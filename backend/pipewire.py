"""
PipeWire Native Audio Module.

Provides low-latency recording (with VAD and pre-roll) and streaming playback
using Debian PipeWire CLI tools (`pw-record` and `pw-play`) without external C dependencies.
"""

import collections
import queue
import subprocess
import threading
import time
from typing import Callable, Optional
import numpy as np
from backend.config import logger


class PipeWirePlayer:
    """Streams raw PCM int16 audio directly to PipeWire via pw-play."""

    def __init__(self, sample_rate: int = 22050, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._current_proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def play_stream(self, chunk_generator) -> bool:
        """
        Play audio chunks from an iterator/generator in real time.
        Returns True if played to completion, False if interrupted.
        """
        cmd = [
            "pw-play",
            "--raw",
            "--rate", str(self.sample_rate),
            "--channels", str(self.channels),
            "--format", "s16",
            "-"
        ]

        with self._lock:
            try:
                self._current_proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                logger.error(f"[PipeWirePlayer] Failed to spawn pw-play: {e}")
                self._current_proc = None
                return False

        proc = self._current_proc
        try:
            for chunk in chunk_generator:
                if proc.poll() is not None:
                    # Process died or was terminated
                    return False
                if chunk and proc.stdin:
                    proc.stdin.write(chunk)
                    proc.stdin.flush()

            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()

            proc.wait()
            return proc.returncode == 0
        except (BrokenPipeError, OSError):
            return False
        except Exception as e:
            logger.error(f"[PipeWirePlayer] Playback error: {e}")
            return False
        finally:
            with self._lock:
                if self._current_proc == proc:
                    self._current_proc = None

    def stop(self):
        """Immediately interrupt any active playback."""
        with self._lock:
            if self._current_proc and self._current_proc.poll() is None:
                try:
                    self._current_proc.terminate()
                    self._current_proc.wait(timeout=0.2)
                except Exception:
                    try:
                        self._current_proc.kill()
                    except Exception:
                        pass
                self._current_proc = None


class PipeWireRecorder:
    """
    Continuous microphone recorder using `pw-record` with built-in
    Voice Activity Detection (VAD) and pre-roll ring buffer.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_samples: int = 512,  # 32ms per chunk
        speech_threshold: float = 0.012,
        silence_duration_s: float = 0.9,
        pre_roll_duration_s: float = 0.4,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_samples = chunk_samples
        self.chunk_bytes = chunk_samples * 2  # 16-bit mono = 2 bytes/sample
        self.speech_threshold = speech_threshold
        self.silence_duration_s = silence_duration_s
        self.max_pre_roll_chunks = max(1, int(pre_roll_duration_s * sample_rate / chunk_samples))
        self.silence_frames_threshold = int(silence_duration_s * sample_rate / chunk_samples)

        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end

        self._utterance_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False

    def start(self):
        """Start the background recording and VAD worker."""
        if self._running:
            return

        cmd = [
            "pw-record",
            "--raw",
            "--rate", str(self.sample_rate),
            "--channels", "1",
            "--format", "s16",
            "-"
        ]

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0
            )
        except Exception as e:
            logger.error(f"[PipeWireRecorder] Failed to spawn pw-record: {e}")
            raise

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def pause(self):
        """Temporarily pause utterance collection (e.g. while AI is speaking)."""
        self._paused = True

    def resume(self):
        """Resume utterance collection."""
        self._paused = False

    def get_utterance(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """Block until a complete speech utterance is captured."""
        try:
            return self._utterance_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _capture_loop(self):
        pre_roll = collections.deque(maxlen=self.max_pre_roll_chunks)
        recorded_chunks = []
        is_speaking = False
        consecutive_speech = 0
        consecutive_silence = 0

        while self._running and self._proc:
            if not self._proc.stdout:
                break

            data = self._proc.stdout.read(self.chunk_bytes)
            if not data or len(data) < self.chunk_bytes:
                if not self._running:
                    break
                time.sleep(0.01)
                continue

            if self._paused:
                pre_roll.clear()
                recorded_chunks.clear()
                is_speaking = False
                consecutive_speech = 0
                consecutive_silence = 0
                continue

            chunk_i16 = np.frombuffer(data, dtype=np.int16)
            rms = float(np.sqrt(np.mean(chunk_i16.astype(np.float32) ** 2))) / 32768.0

            if rms >= self.speech_threshold:
                consecutive_speech += 1
                consecutive_silence = 0

                if consecutive_speech >= 2:
                    if not is_speaking:
                        is_speaking = True
                        recorded_chunks = list(pre_roll) + [chunk_i16]
                        pre_roll.clear()
                        if self.on_speech_start:
                            try:
                                self.on_speech_start()
                            except Exception:
                                pass
                    else:
                        recorded_chunks.append(chunk_i16)
            else:
                consecutive_speech = 0
                if is_speaking:
                    recorded_chunks.append(chunk_i16)
                    consecutive_silence += 1

                    if consecutive_silence >= self.silence_frames_threshold:
                        # Utterance finished
                        is_speaking = False
                        consecutive_silence = 0
                        if self.on_speech_end:
                            try:
                                self.on_speech_end()
                            except Exception:
                                pass

                        # Require minimum 0.25s of audio to prevent false triggers
                        min_samples = int(self.sample_rate * 0.25)
                        total_samples = sum(len(c) for c in recorded_chunks)
                        if total_samples >= min_samples:
                            merged = np.concatenate(recorded_chunks)
                            audio_float32 = merged.astype(np.float32) / 32768.0
                            self._utterance_queue.put(audio_float32)

                        recorded_chunks.clear()
                else:
                    pre_roll.append(chunk_i16)

    def stop(self):
        """Stop recorder and terminate subprocess."""
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=0.3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

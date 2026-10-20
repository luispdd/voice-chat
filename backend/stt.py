"""
Speech-to-Text (STT) service utilizing whisper.cpp (Whisper small, ggml).
"""

import io
import re
from typing import Optional
import numpy as np
import soundfile as sf
from pydub import AudioSegment
from pywhispercpp.model import Model
from backend import config
from backend.config import logger

_stt_model: Optional[Model] = None


def get_stt_model() -> Model:
    """Warmup and initialize whisper.cpp Model singleton."""
    global _stt_model
    if _stt_model is None:
        model_name = getattr(config, "STT_MODEL_NAME", "small.en")
        logger.info(f"📦 Initializing Whisper STT Model ({model_name})...")
        _stt_model = Model(model_name, print_progress=False, print_realtime=False)
        try:
            _stt_model.transcribe(np.zeros(16000, dtype=np.float32))
        except Exception as e:
            logger.info(f"⚠️ STT warmup info: {e}")
        logger.info(f"✅ Whisper STT Model ({model_name}) initialized.")
    return _stt_model


def init_stt():
    """Explicit initializer for server lifespan startup."""
    get_stt_model()


def _run_whisper(model: Model, audio: np.ndarray) -> str:
    segments = model.transcribe(audio.astype(np.float32), no_context=True)
    text = " ".join(s.text.strip() for s in segments)
    # Drop non-speech tags such as [BLANK_AUDIO], (music), [ Silence ]
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", text)
    return " ".join(text.split())


def audio_bytes_to_float32(audio_bytes: bytes) -> np.ndarray:
    """
    Convert incoming audio bytes (WAV, WebM, MP3, etc.) to 16kHz mono float32 numpy array
    using pydub AudioSegment and soundfile fallback.
    """
    if not audio_bytes or len(audio_bytes) < 100:
        return np.zeros(0, dtype=np.float32)

    # 1. Primary path: AudioSegment
    try:
        audio_stream = io.BytesIO(audio_bytes)
        audio_seg = AudioSegment.from_file(audio_stream)
        audio_seg = audio_seg.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        raw_samples = audio_seg.get_array_of_samples()
        audio_np = np.array(raw_samples, dtype=np.float32) / 32768.0
    except Exception as pydub_err:
        # Fallback to soundfile if AudioSegment fails
        try:
            with sf.SoundFile(io.BytesIO(audio_bytes)) as f:
                audio = f.read(dtype="float32")
                samplerate = f.samplerate
                if audio.ndim > 1:
                    audio = np.mean(audio, axis=1)
                if samplerate != 16000:
                    pcm_data = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
                    audio_seg = AudioSegment(
                        pcm_data,
                        frame_rate=samplerate,
                        sample_width=2,
                        channels=1,
                    ).set_frame_rate(16000)
                    audio_np = np.array(audio_seg.get_array_of_samples(), dtype=np.float32) / 32768.0
                else:
                    audio_np = audio
        except Exception as sf_err:
            logger.error(f"[STT Diagnostics] Audio conversion failed. pydub_err: {pydub_err}, sf_err: {sf_err}")
            raise

    # Remove DC offset
    if len(audio_np) > 0:
        audio_np = audio_np - np.mean(audio_np)

    duration = len(audio_np) / 16000
    peak = float(np.max(np.abs(audio_np))) if len(audio_np) > 0 else 0.0
    rms = float(np.sqrt(np.mean(audio_np**2))) if len(audio_np) > 0 else 0.0
    logger.info(f"[STT Diagnostics] Audio: 16000Hz mono, Duration: {duration:.3f}s, Peak: {peak:.3f}, RMS: {rms:.3f}")

    return audio_np


def trim_silence(
    audio: np.ndarray,
    samplerate: int = 16000,
    frame_duration_ms: int = 30,
    padding_ms: int = 250,
) -> np.ndarray:
    """
    Trim extended leading and trailing silence from audio to prevent decoder
    early-termination on long leading pauses.
    """
    if len(audio) == 0:
        return audio

    frame_size = int(samplerate * frame_duration_ms / 1000)
    padding_samples = int(samplerate * padding_ms / 1000)

    num_frames = len(audio) // frame_size
    if num_frames == 0:
        return audio

    frames = audio[:num_frames * frame_size].reshape(num_frames, frame_size)
    frame_rms = np.sqrt(np.mean(frames ** 2, axis=1))

    max_rms = np.max(frame_rms)
    if max_rms < 0.005:  # Audio is essentially pure silence
        return audio

    threshold = max(0.008, max_rms * 0.05)
    active_frames = np.where(frame_rms > threshold)[0]
    if len(active_frames) == 0:
        return audio

    start_idx = max(0, active_frames[0] * frame_size - padding_samples)
    end_idx = min(len(audio), (active_frames[-1] + 1) * frame_size + padding_samples)

    return audio[start_idx:end_idx]


def transcribe_voice_bytes(raw_audio_payload: bytes) -> str:
    """
    Transcribe raw audio bytes into text using Whisper (whisper.cpp).

    Args:
        raw_audio_payload: In-memory raw audio bytes from client microphone.

    Returns:
        Transcribed text string.
    """
    if not raw_audio_payload:
        logger.info("[STT Diagnostics] Empty audio payload received.")
        return ""

    try:
        audio_data = audio_bytes_to_float32(raw_audio_payload)
    except Exception as e:
        logger.error(f"[STT Diagnostics] Failed to decode audio bytes: {e}")
        return ""

    duration = len(audio_data) / 16000
    if len(audio_data) < 1600:  # Less than 0.1s
        logger.info(f"[STT Diagnostics] Audio segment too short: {len(audio_data)} samples ({duration:.3f}s)")
        return ""

    trimmed_audio = trim_silence(audio_data)
    trimmed_duration = len(trimmed_audio) / 16000
    if len(trimmed_audio) < 1600:
        logger.info(f"[STT Diagnostics] Audio only contains silence: {duration:.3f}s -> {trimmed_duration:.3f}s")
        return ""

    if trimmed_duration < duration:
        logger.info(f"[STT Diagnostics] Trimmed silence: {duration:.3f}s -> {trimmed_duration:.3f}s")

    if len(trimmed_audio) > 60 * 16000:
        logger.info(f"[STT Diagnostics] Audio segment too long ({trimmed_duration:.3f}s). Truncating to 60s.")
        trimmed_audio = trimmed_audio[:60 * 16000]

    model = get_stt_model()

    try:
        text = _run_whisper(model, trimmed_audio)

        # Retry fallback with peak normalization if result is empty on audible speech
        if not text and float(np.sqrt(np.mean(trimmed_audio**2))) > 0.01:
            peak = float(np.max(np.abs(trimmed_audio)))
            if peak > 0:
                text = _run_whisper(model, (trimmed_audio / peak) * 0.95)

        logger.info(f"[STT Diagnostics] Decoded Text: '{text}'")
        return text
    except Exception as e:
        logger.error(f"[STT Diagnostics] Error transcribing audio: {e}")
        return ""


# Alias for compatibility with new-voice-chat services
transcribe_audio = transcribe_voice_bytes
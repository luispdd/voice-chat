import os
import subprocess
from faster_whisper import WhisperModel

stt_model = None

def init_stt():
    global stt_model
    print("📥 Initializing Faster-Whisper Engine (tiny.en)...")
    # compute_type="int8" forces CPU quantization for blazing-fast local speed
    stt_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    print("✅ Faster-Whisper Engine Online.")

def transcribe_voice_bytes(temp_raw_input: str, temp_wav_output: str) -> str:
    global stt_model
    
    if stt_model is None:
        print("⚠️ Warning: Faster-Whisper model was None! Initializing fallback...")
        stt_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

    try:
        # Faster-Whisper handles various audio rates, but sticking to 16kHz is standard
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", temp_raw_input,
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            temp_wav_output
        ]
        subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Transcribe returns an iterable generator of segments
        segments, info = stt_model.transcribe(temp_wav_output, beam_size=1)
        
        # Collapse text segments into a single string
        user_text = " ".join([segment.text for segment in segments]).strip()
        return user_text
        
    except Exception as e:
        print(f"🚨 Faster-Whisper Processing Exception: {e}")
        return ""
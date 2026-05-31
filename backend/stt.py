import io
import numpy as np
from pydub import AudioSegment
from faster_whisper import WhisperModel

stt_model = None

def init_stt():
    global stt_model
    print("📥 Initializing Faster-Whisper Engine (tiny.en)...")
    stt_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    print("✅ Faster-Whisper Engine Online.")

def transcribe_voice_bytes(raw_audio_payload: bytes) -> str:
    global stt_model
    
    if stt_model is None:
        print("⚠️ Warning: Faster-Whisper model was None! Reinitializing...")
        stt_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

    try:
        if not raw_audio_payload or len(raw_audio_payload) < 100:
            return ""

        # Load the bytes completely in RAM memory space
        audio_stream = io.BytesIO(raw_audio_payload)
        audio_segment = AudioSegment.from_file(audio_stream)
        
        # CRITICAL FIX: Re-assign the modified segments so the track changes apply!
        audio_segment = audio_segment.set_frame_rate(16000)
        audio_segment = audio_segment.set_channels(1)
        audio_segment = audio_segment.set_sample_width(2) # Force 16-bit PCM execution
            
        # Extract the now verified 16-bit single track samples
        raw_samples = audio_segment.get_array_of_samples()
        
        # Safely normalize 16-bit signed integers to a float32 matrix between -1.0 and 1.0
        audio_np = np.array(raw_samples, dtype=np.float32) / 32768.0

        # Run clean inference on the flat, verified mono waveform array
        segments, _ = stt_model.transcribe(
            audio_np, 
            beam_size=1, 
            language="en",
            vad_filter=True,
            vad_parameters=dict(min_speech_duration_ms=250),
            condition_on_previous_text=False
        )
        
        user_text = " ".join([segment.text for segment in segments]).strip()
        return user_text
        
    except Exception as e:
        print(f"🚨 Faster-Whisper Memory Processing Exception: {e}")
        return ""
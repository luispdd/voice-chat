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
        init_stt()

    try:
        if not raw_audio_payload or len(raw_audio_payload) < 100:
            return ""

        audio_stream = io.BytesIO(raw_audio_payload)
        audio_segment = AudioSegment.from_file(audio_stream)
        
        audio_segment = audio_segment.set_frame_rate(16000)
        audio_segment = audio_segment.set_channels(1)
        audio_segment = audio_segment.set_sample_width(2)
            
        raw_samples = audio_segment.get_array_of_samples()
        audio_np = np.array(raw_samples, dtype=np.float32) / 32768.0

        segments, _ = stt_model.transcribe(
            audio_np, 
            beam_size=1, 
            language="en",
            vad_filter=True,
            vad_parameters=dict(min_speech_duration_ms=250),
            condition_on_previous_text=False
        )
        
        return " ".join([segment.text for segment in segments]).strip()
        
    except Exception as e:
        print(f"🚨 Faster-Whisper Exception: {e}")
        return ""
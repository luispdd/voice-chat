import io
import numpy as np
from pydub import AudioSegment
import moonshine_onnx
from moonshine_onnx import MoonshineOnnxModel

stt_model = None

def init_stt():
    global stt_model
    print("📥 Initializing Moonshine Engine (base, CPU via ONNX)...")
    stt_model = MoonshineOnnxModel(model_name="base")
    print("✅ Moonshine Engine Online.")

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
        if not raw_samples or len(raw_samples) < 1600:  # Minimum 0.1s at 16kHz
            return ""
            
        audio_np = np.array(raw_samples, dtype=np.float32) / 32768.0

        # Moonshine supports segments up to 64s
        max_samples = 16000 * 64
        if len(audio_np) > max_samples:
            audio_np = audio_np[:max_samples]

        transcriptions = moonshine_onnx.transcribe(audio_np, model=stt_model)
        
        if not transcriptions:
            return ""
            
        return " ".join([t.strip() for t in transcriptions if t.strip()]).strip()
        
    except Exception as e:
        print(f"🚨 Moonshine Exception: {e}")
        return ""
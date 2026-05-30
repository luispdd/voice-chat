import os
import subprocess
import sys
import moonshine_onnx

stt_model = None

def init_stt():
    global stt_model
    print("📥 Initializing Moonshine ONNX Transformer Engine...")
    stt_model = moonshine_onnx.MoonshineOnnxModel(model_name="moonshine/tiny")
    print(f"✅ Moonshine ONNX Engine Online. Object ID: {id(stt_model)}")
    
    if hasattr(stt_model, 'warmup'):
        stt_model.warmup()

def transcribe_voice_bytes(temp_raw_input: str, temp_wav_output: str) -> str:
    global stt_model
    
    # FAIL-SAFE: If Python module namespace splitting caused stt_model to be lost,
    # reload it instantly on demand so the user never encounters a NoneType crash.
    if stt_model is None:
        print("⚠️ Warning: stt_model was None at runtime! Forcing emergency initialization...")
        stt_model = moonshine_onnx.MoonshineOnnxModel(model_name="moonshine/tiny")

    try:
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", temp_raw_input,
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            temp_wav_output
        ]
        subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Explicitly pass our verified model object instance
        transcription_list = moonshine_onnx.transcribe(temp_wav_output, model=stt_model)
        return transcription_list[0].strip() if transcription_list else ""
    except Exception as e:
        print(f"🚨 Moonshine Processing Exception: {e}")
        return ""
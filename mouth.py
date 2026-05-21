import os
import sys
import json
import numpy as np
import sounddevice as sd
import onnxruntime as ort
from piper.voice import PiperVoice
from piper.config import PiperConfig

def speak_text(text: str) -> None:
    """Synthesizes text into speech cleanly and sequentially using the Piper engine."""
    if not text.strip():
        return

    model_path = os.path.join("voice_models", "en_US-amy-medium.onnx")
    config_path = model_path + ".json"
    
    if not os.path.exists(model_path) or not os.path.exists(config_path):
        print(f"\n🚨 Mouth Error: Missing files in 'voice_models/'", file=sys.stderr)
        return

    try:
        # Our stable 2-thread configuration to protect your laptop's power supply
        sess_opt = ort.SessionOptions()
        sess_opt.intra_op_num_threads = 2
        sess_opt.inter_op_num_threads = 2
        
        session = ort.InferenceSession(model_path, sess_opt, providers=["CPUExecutionProvider"])
        
        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
        voice_config = PiperConfig.from_dict(config_dict)
        
        voice = PiperVoice(config=voice_config, session=session)
        sample_rate = voice.config.sample_rate
        
        # Stream the audio data directly to your speakers
        with sd.OutputStream(samplerate=sample_rate, channels=1, dtype='float32') as stream:
            for chunk in voice.synthesize(text):
                raw_bytes = chunk.audio_int16_bytes
                audio_array_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
                audio_array_float32 = audio_array_int16.astype(np.float32) / 32768.0
                stream.write(audio_array_float32)
                
    except Exception as e:
        print(f"\n🚨 TTS Streaming Runtime Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    print("Testing local standalone mouth module...")
    speak_text("System check. Sequential speech initialization complete.")

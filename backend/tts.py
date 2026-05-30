import os
import json
import onnxruntime as ort
from piper.voice import PiperVoice
from piper.config import PiperConfig

voice = None

def init_tts():
    global voice
    print("📥 Initializing Piper TTS Engine...")
    model_path = os.path.join("voice_models", "en_US-amy-medium.onnx")
    
    sess_opt = ort.SessionOptions()
    sess_opt.intra_op_num_threads = 2
    sess_opt.inter_op_num_threads = 2
    session = ort.InferenceSession(model_path, sess_opt, providers=["CPUExecutionProvider"])

    with open(model_path + ".json", "r", encoding="utf-8") as f:
        config_dict = json.load(f)
        
    voice = PiperVoice(config=PiperConfig.from_dict(config_dict), session=session)
    print("✅ Piper TTS Engine Online.")

    for _ in voice.synthesize("Online"):
        pass

def generate_speech_bytes(text_sentence: str) -> bytes:
    """Synthesizes a sentence string into raw PCM int16 bytes with length framing."""
    global voice
    
    # FAIL-SAFE: Reconstruct the Piper engine instance instantly on-demand 
    # if Uvicorn's reload thread lost track of the global reference.
    if voice is None:
        print("⚠️ Warning: voice engine was None at runtime! Forcing emergency initialization...")
        model_path = os.path.join("voice_models", "en_US-amy-medium.onnx")
        sess_opt = ort.SessionOptions()
        sess_opt.intra_op_num_threads = 2
        sess_opt.inter_op_num_threads = 2
        session = ort.InferenceSession(model_path, sess_opt, providers=["CPUExecutionProvider"])

        with open(model_path + ".json", "r", encoding="utf-8") as f:
            config_dict = json.load(f)
            
        voice = PiperVoice(config=PiperConfig.from_dict(config_dict), session=session)

    output_buffer = b""
    for audio_chunk in voice.synthesize(text_sentence):
        raw_bytes = audio_chunk.audio_int16_bytes
        length_prefix = len(raw_bytes).to_bytes(4, byteorder='big')
        output_buffer += b"AUDIO:" + length_prefix + raw_bytes
    return output_buffer
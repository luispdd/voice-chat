import json
import os
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from piper.config import PiperConfig
from piper.voice import PiperVoice

voice = None

# Centralized Voice Model Repository Settings
HF_REPO_ID = "rhasspy/piper-voices"
HF_MODEL_FILE = "en/en_GB/cori/high/en_GB-cori-high.onnx"
HF_CONFIG_FILE = "en/en_GB/cori/high/en_GB-cori-high.onnx.json"


def _load_piper_voice() -> PiperVoice:
    """Helper to fetch model via HF Hub and build tuned ONNX Piper instance."""
    print(f"📦 Verifying/Downloading Piper Voice Model ({HF_REPO_ID})...")

    # Downloads to HF cache directory (~/.cache/huggingface/hub/) and returns absolute local paths
    model_path = hf_hub_download(repo_id=HF_REPO_ID, filename=HF_MODEL_FILE)
    config_path = hf_hub_download(repo_id=HF_REPO_ID, filename=HF_CONFIG_FILE)

    sess_opt = ort.SessionOptions()
    sess_opt.intra_op_num_threads = 2
    sess_opt.inter_op_num_threads = 2
    session = ort.InferenceSession(
        model_path, sess_opt, providers=["CPUExecutionProvider"]
    )

    with open(config_path, "r", encoding="utf-8") as f:
        config_dict = json.load(f)

    return PiperVoice(config=PiperConfig.from_dict(config_dict), session=session)


def init_tts():
    """Initializes and warms up the Piper TTS Engine."""
    global voice
    if voice is not None:
        return

    print("📥 Initializing Piper TTS Engine...")
    voice = _load_piper_voice()
    print("✅ Piper TTS Engine Online.")

    # Warm-up run to eliminate latency on first real request
    for _ in voice.synthesize("Online"):
        pass


def generate_speech_bytes(text_sentence: str) -> bytes:
    """Synthesizes a sentence string into raw PCM int16 bytes with length framing."""
    global voice

    # FAIL-SAFE: Reconstruct engine instance on-demand if Uvicorn reload cleared global
    if voice is None:
        print(
            "⚠️ Warning: voice engine was None at runtime! Forcing emergency initialization..."
        )
        voice = _load_piper_voice()

    output_buffer = b""
    for audio_chunk in voice.synthesize(text_sentence):
        raw_bytes = audio_chunk.audio_int16_bytes
        length_prefix = len(raw_bytes).to_bytes(4, byteorder="big")
        output_buffer += b"AUDIO:" + length_prefix + raw_bytes

    return output_buffer
"""
Text-to-Speech (TTS) Synthesis Engine.

Converts text to raw PCM int16 audio bytes with length framing.
Uses Piper TTS for synthesis.

Usage:
    from backend.common.tts import init_tts, generate_speech_bytes
    
    init_tts()  # Initialize and warm-up
    audio_bytes = generate_speech_bytes("Hello world")
"""

from typing import Optional
from piper.voice import PiperVoice
from backend.common.model_manager import load_piper_voice_model

# Global TTS instance managed by init_tts()
_tts_instance: Optional[PiperVoice] = None


def init_tts(voice_model: Optional[PiperVoice] = None) -> None:
    """
    Initialize Piper TTS engine and warm it up.
    
    Args:
        voice_model: Optional pre-loaded PiperVoice. If None, loads default model.
    """
    global _tts_instance
    if _tts_instance is not None:
        return

    print("📥 Initializing Piper TTS Engine...")
    _tts_instance = voice_model or load_piper_voice_model()
    print("✅ Piper TTS Engine Online.")

    # Warm-up run to eliminate latency on first real request
    for _ in _tts_instance.synthesize("Online"):
        pass


def generate_speech_bytes(text_sentence: str) -> bytes:
    """
    Synthesize text to raw PCM int16 bytes with length framing.
    
    Output format: b"AUDIO:<4-byte-length><raw_pcm_bytes>..."
    
    Args:
        text_sentence: Text to convert to speech
    
    Returns:
        Binary audio buffer with framed PCM data
    
    Raises:
        RuntimeError: If TTS engine not initialized
    """
    global _tts_instance

    # Fail-safe: reinitialize if module was reloaded (e.g., Uvicorn reload)
    if _tts_instance is None:
        print("⚠️ Warning: TTS engine was None! Forcing emergency initialization...")
        _tts_instance = load_piper_voice_model()

    output_buffer = b""
    for audio_chunk in _tts_instance.synthesize(text_sentence):
        raw_bytes = audio_chunk.audio_int16_bytes
        length_prefix = len(raw_bytes).to_bytes(4, byteorder="big")
        output_buffer += b"AUDIO:" + length_prefix + raw_bytes

    return output_buffer

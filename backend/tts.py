"""
TTS Module - Adapter for backend.common.tts to voice-chat usage.

Wraps common.tts functions for voice-chat endpoint calls.
"""

from backend.common import tts as common_tts


def init_tts():
    """Initialize TTS engine with defaults."""
    common_tts.init_tts()


def generate_speech_bytes(text_sentence: str) -> bytes:
    """Synthesize text to speech bytes."""
    return common_tts.generate_speech_bytes(text_sentence)


__all__ = ["init_tts", "generate_speech_bytes"]

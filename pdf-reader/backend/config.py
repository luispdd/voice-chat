"""
Voice-Chat Configuration.

Imports shared configuration from backend.common and adds voice-chat specific settings.
"""

from backend.common.config import setup_logger, Config

# [VOICE-CHAT SPECIFIC] - Initialize logger with project name
logger = setup_logger("voice_companion")

# [VOICE-CHAT SPECIFIC] - Voice Assistant System Instructions
SYSTEM_INSTRUCTIONS = (
    "You are an empathetic, concise, and intelligent voice assistant. "
    "Do NOT output thinking steps, reasoning traces, markdown formatting (like asterisks or bold text), "
    "or emojis. Speak in natural, plain text, keeping responses direct and under 3 sentences."
)

# Initialize shared configuration
config_instance = Config("voice_companion", logger)
ENGINE = config_instance.ENGINE
MODEL = config_instance.MODEL
PORT = config_instance.PORT
HOST_IP = config_instance.HOST_IP
BASE_URL = config_instance.BASE_URL
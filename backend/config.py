import os
import socket
import logging

# Configure global timestamped logger (HH:MM:SS format)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("voice_companion")

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

ENGINE = os.getenv("ENGINE", "lm-studio").lower()
MODEL = os.getenv("MODEL", "google/gemma-3-4b-it-qat")
PORT = int(os.getenv("PORT", "8000"))
HOST_IP = get_local_ip()

if ENGINE == "ollama":
    BASE_URL = "http://localhost:11434/v1"
else:
    BASE_URL = "http://localhost:1234/v1"

SYSTEM_INSTRUCTIONS = (
    "You are an empathetic, concise, and intelligent voice assistant. "
    "Do NOT output thinking steps, reasoning traces, markdown formatting (like asterisks or bold text), "
    "or emojis. Speak in natural, plain text, keeping responses direct and under 3 sentences."
)
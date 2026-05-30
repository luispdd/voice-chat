import socket

# Global configuration placeholders
ENGINE = "lm-studio"
MODEL = "google/gemma-3-4b-it-qat"
BASE_URL = "http://127.0.0.1:1234/v1"
PORT = 8000
HOST_IP = "127.0.0.1"

SYSTEM_INSTRUCTIONS = (
    "You are a helpful, brief web voice assistant. Keep answers short and conversational. "
    "Do not use bullet points, asterisks, or special markdown characters."
)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    return local_ip

def initialize_global_settings(engine: str, model: str, port: int = 8000):
    global ENGINE, MODEL, BASE_URL, PORT, HOST_IP
    ENGINE = engine
    MODEL = model
    PORT = port
    HOST_IP = get_local_ip()
    
    # Dynamically pivot the API port mapping depending on selected target engine
    if engine == "ollama":
        BASE_URL = "http://127.0.0.1:11434/v1"
    else:
        BASE_URL = "http://127.0.0.1:1234/v1"
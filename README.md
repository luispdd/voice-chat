# Offline Voice Companion

An offline, low-latency, hands-free web voice assistant that runs entirely on your local machine. This project utilizes a streaming architecture to handle real-time speech-to-text (STT), large language model (LLM) text token streaming, and sentence-by-sentence text-to-speech (TTS) synthesis back to the browser.

---

## Project Architecture & Directory Structure

The project has been refactored into a highly modular layout following Python best practices. This separating of concerns isolates individual tasks (Server routing, Audio Transcription, LLM Streaming, Voice Synthesis) into self-contained modules.

voice-chatbot/
├── backend/                   # Main Python application package
│   ├── __init__.py            # Declares directory as a Python module
│   ├── config.py              # Handles command-line arguments and global variables
│   ├── llm.py                 # Connects to OpenAI-compatible endpoints (Ollama / LM Studio)
│   ├── server.py              # Manages FastAPI server instance and HTTP streaming routes
│   ├── stt.py                 # Loads and executes Moonshine ONNX transcription
│   └── tts.py                 # Loads and executes Piper TTS voice engine
├── static/                    # Frontend client assets
│   ├── app.js                 # 60fps VAD monitor and binary audio router stream buffer
│   └── style.css              # Dark-mode interface styles
├── voice_models/              # Neural network voice profile storage
│   ├── en_US-amy-medium.onnx  # Piper model weight checkpoints
│   └── en_US-amy-medium.onnx.json
├── cert.pem                   # Local SSL Certificate for secure microphone access
├── key.pem                    # Local SSL Private Key
├── index.html                 # Main interface markup shell
└── main.py                    # Entrypoint configuration launch script

---

## Core Engine Components

1. Frontend Voice Activity Detection (VAD): A continuous browser Web Audio monitor loop that detects vocal volume spikes, records fragments, and ships them over HTTP only when you stop speaking.
2. Audio Transcription (STT): Moonshine ONNX (Tiny) processes incoming chunks within milliseconds.
3. Inference Pipeline (LLM): Communicates token-by-token with your local inference backend via a streaming connection.
4. Speech Synthesis (TTS): Piper TTS slices text sequences along syntax boundaries and streams raw PCM sound waves (22050Hz, Mono, Int16) back to the web client.

---

## Prerequisite Verification

Ensure you have your environment variables and model weights set up correctly in the directory before boot:
* FFmpeg: Must be installed on your local host system and registered to your global system path variables so Python can spawn audio conversion subprocesses.
* SSL Certificates: Secure Context execution requirements (https://) mandate that cert.pem and key.pem live in the root directory for remote mobile or LAN connections to successfully fetch microphone access permissions.

---

## 💻 Commands Required to Run the Project

Always initiate the runtime using the `main.py` entrypoint script via `uv run`. To ensure your custom engine and model arguments are passed directly to the Python script instead of being intercepted by the package manager, you must use either the explicit interpreter syntax or the double-dash (`--`) separator.

### 1. Launch with LM Studio (Default)
To run using LM Studio, make sure your application server is running locally on port 1234 with an active model loaded:

uv run main.py

* Engine used: LM Studio (http://127.0.0.1:1234/v1)
* Default model string: google/gemma-3-4b-it-qat

### 2. Launch with a Custom Model or Alternative Tag
You can dynamically target any model currently available on your local system without editing the Python source code by appending your arguments after a double-dash (`--`).

* For LM Studio: Match the model identifier displayed at the top of your LM Studio application window.
  uv run main.py -- --model microsoft/Phi-4-mini-instruct

* For Ollama: Match the tag name used when downloading the weights via your terminal.
  uv run main.py -- --engine ollama --model qwen3.5:9b

* Alternative syntax (Explicit Python call):
  uv run python main.py --engine ollama --model qwen3.5:9b

### 3. Launch with Ollama
To switch your entire streaming text infrastructure over to Ollama, make sure the Ollama daemon service is active on your host platform (11434):

python main.py --engine ollama --model llama3

* Engine used: Ollama (http://127.0.0.1:11434/v1)
* Model targeted: llama3 (or any valid tag downloaded via ollama run)

### 4. Adjust the Hosting Channel Port
By default, the dashboard is served over port 8000. If that slot is blocked by another task, alter it using the --port flag:

python main.py --port 8500

---

## Accessing Across Your Home Network

Upon initialization, the bootloader automatically displays your local network footprint. 

============================================================
🚀 OFFLINE VOICE COMPANION ACTIVE AND WARMED UP
============================================================
🏠 Web Console App URL:      https://127.0.0.1:8000
📱 Local Area Network URL:   https://192.168.1.50:8000
🧠 Selected Model Target:    [OLLAMA] -> llama3
============================================================

Navigate to the Local Area Network URL printed on your terminal screen from any phone, laptop, or tablet sharing your Wi-Fi network to use the assistant on other devices!
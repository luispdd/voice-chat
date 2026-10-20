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
2. Audio Transcription (STT): Whisper (whisper.cpp via `pywhispercpp==1.5.1`, default `small.en`) processes incoming chunks with high accuracy and low latency.
3. Inference Pipeline (LLM): Communicates token-by-token with OpenAI, Ollama, LM Studio, OpenRouter, or custom OpenAI-compatible endpoints.
4. Speech Synthesis (TTS): Piper TTS slices text sequences along syntax boundaries and streams raw PCM sound waves (22050Hz, Mono, Int16) back to the web client.

---

## Prerequisite Verification

Ensure you have your environment variables and model weights set up correctly in the directory before boot:
* FFmpeg: Must be installed on your local host system and registered to your global system path variables so Python can spawn audio conversion subprocesses.
* SSL Certificates: Secure Context execution requirements (https://) mandate that cert.pem and key.pem live in the root directory for remote mobile or LAN connections to successfully fetch microphone access permissions.

---

## 💻 Commands Required to Run the Project

Always initiate the runtime using the `main.py` entrypoint script via `uv run`.

### 1. Launch with OpenAI API
To run with official OpenAI API:

```bash
uv run python main.py --engine openai --model gpt-4o-mini --api-key "sk-..."
```

* Engine used: OpenAI (https://api.openai.com/v1)
* Default model: `gpt-4o-mini`

### 2. Launch with a Custom OpenAI-Compatible Server (e.g. Local Proxy or vLLM)
You can target any OpenAI-compatible server URL:

```bash
uv run python main.py --engine openai --base-url http://127.0.0.1:8888/v1 --model custom-model --api-key not-needed
```

### 3. Launch with LM Studio (Default)
To run using LM Studio, make sure your application server is running locally on port 1234:

```bash
uv run python main.py
```

* Engine used: LM Studio (http://127.0.0.1:1234/v1)
* Default model: `google/gemma-3-4b-it-qat`

### 4. Launch with Ollama
To switch your streaming text infrastructure over to Ollama:

```bash
uv run python main.py --engine ollama --model llama3
```

* Engine used: Ollama (http://127.0.0.1:11434/v1)
* Model targeted: `llama3`

### 5. Custom Whisper STT Model
By default, the STT service uses `small.en`. You can choose another Whisper GGML model:

```bash
uv run python main.py --stt-model base.en
```

### 6. Adjust the Hosting Channel Port
By default, the dashboard is served over port 8000:

```bash
uv run python main.py --port 8500
```

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
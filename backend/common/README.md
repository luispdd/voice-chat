# Backend Common Modules

This folder contains reusable modules that can be shared across multiple projects (e.g., voice-chat, pdf-narrator).

## Files

- **config.py** — Environment-based configuration (ENGINE, MODEL, PORT, HOST_IP, BASE_URL)
- **model_manager.py** — Piper TTS model download and caching from HuggingFace Hub
- **tts.py** — Text-to-Speech synthesis engine (text → PCM bytes)
- **llm.py** — LLM client and streaming abstraction (Ollama/LM-Studio compatible)

## Project-Specific Setup

All modules in this folder are **project-agnostic**. Each project using these modules should:

### 1. Copy `backend/common/` to your project
```bash
cp -r voice-chat/backend/common your-new-project/backend/
```

### 2. Create project-specific `backend/config.py` wrapper

Example for a new project (e.g., pdf-narrator):

```python
# pdf-narrator/backend/config.py

from backend.common.config import setup_logger, Config

# [VOICE-CHAT SPECIFIC] - Initialize logger with PDF narrator project name
logger = setup_logger("pdf_narrator")

# [VOICE-CHAT SPECIFIC] - Project-specific system instructions
SYSTEM_INSTRUCTIONS = (
    "You are a professional book narrator. "
    "Read the provided text clearly and naturally. "
    "Do NOT add commentary or explanations."
)

# Initialize shared configuration from common/
config_instance = Config("pdf_narrator", logger)

# Re-export config values for convenience
ENGINE = config_instance.ENGINE
MODEL = config_instance.MODEL
PORT = config_instance.PORT
HOST_IP = config_instance.HOST_IP
BASE_URL = config_instance.BASE_URL
```

### 3. Import in your server

```python
# pdf-narrator/backend/server.py

from backend import config
from backend.common import tts, llm

# Use config values:
# - config.ENGINE, config.MODEL, config.PORT, config.BASE_URL
# - config.SYSTEM_INSTRUCTIONS

# Initialize engines:
# - tts.init_tts()
# - llm.init_llm(config.ENGINE, config.BASE_URL)

# Use functions:
# - audio_bytes = tts.generate_speech_bytes("text")
# - stream = await llm.get_chat_stream(messages, config.MODEL)
```

## Updating Common Code

If you fix bugs or improve modules in `backend/common/`:

1. Test in your project (e.g., voice-chat)
2. Copy changes to other projects using these modules (e.g., pdf-narrator)
3. Optionally extract to shared pip package in future

## No Project-Specific Code in `backend/common/`

All files in this folder are meant to be copied as-is. Any project-specific logic belongs in:
- `backend/config.py` (wrapper, project config)
- `backend/server.py` (project routes)
- Other project-specific modules

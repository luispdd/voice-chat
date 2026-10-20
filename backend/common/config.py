"""
Shared Configuration Management.

This module handles:
- Environment variable parsing (ENGINE, MODEL, PORT)
- Logger initialization with configurable project name
- Network discovery (local IP detection)
- LLM base URL routing based on engine selection

Usage:
    from backend.common.config import setup_logger, Config
    
    logger = setup_logger("my_project")
    config = Config("my_project", logger)
"""

import os
import socket
import logging


def setup_logger(project_name: str = "app") -> logging.Logger:
    """
    Initialize timestamped logger with project name.
    
    Args:
        project_name: Name for logger (e.g., "voice_companion", "pdf_narrator")
    
    Returns:
        Configured logger instance
    """
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    return logging.getLogger(project_name)


def get_local_ip() -> str:
    """
    Detect local IP address for mDNS/LAN discovery.
    
    Returns:
        Local IP string, or "127.0.0.1" if detection fails
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


class Config:
    """
    LLM engine, model, and STT configuration from environment variables.
    
    Attributes:
        ENGINE: "lm-studio", "ollama", "openai", or "openrouter" (default: "lm-studio")
        MODEL: Target model identifier (default depends on engine)
        PORT: Server port (default: 8000)
        HOST_IP: Local IP address
        BASE_URL: LLM API endpoint
        API_KEY: Provider API key
        STT_MODEL_NAME: Whisper.cpp model name or path (default: "small.en")
    """
    
    def __init__(self, project_name: str = "app", logger: logging.Logger = None):
        """
        Initialize configuration.
        
        Args:
            project_name: Project identifier (for logging)
            logger: Optional logger instance. If None, creates new one.
        """
        self.project_name = project_name
        self.logger = logger or setup_logger(project_name)
        
        # Load from environment variables
        raw_engine = os.getenv("ENGINE", os.getenv("LLM_ENGINE", "lm-studio")).lower()
        self.ENGINE = "lm-studio" if raw_engine in ("lmstudio", "lm-studio") else raw_engine
        self.PORT = int(os.getenv("PORT", "8000"))
        self.HOST_IP = get_local_ip()
        
        # Route default base URL by engine
        if self.ENGINE == "ollama":
            default_base_url = "http://localhost:11434/v1"
        elif self.ENGINE == "openai":
            default_base_url = "https://api.openai.com/v1"
        elif self.ENGINE == "openrouter":
            default_base_url = "https://openrouter.ai/api/v1"
        else:  # lm-studio default
            default_base_url = "http://localhost:1234/v1"
            
        self.BASE_URL = os.getenv("BASE_URL", os.getenv("LLM_BASE_URL", default_base_url))

        # Route default model by engine
        if self.ENGINE == "openai":
            default_model = "gpt-4o-mini"
        elif self.ENGINE == "ollama":
            default_model = "llama3"
        elif self.ENGINE == "openrouter":
            default_model = "meta-llama/llama-3.3-70b-instruct"
        else:
            default_model = "google/gemma-3-4b-it-qat"
            
        self.MODEL = os.getenv("MODEL", os.getenv("LLM_MODEL", default_model))
        self.API_KEY = os.getenv("API_KEY", os.getenv("LLM_API_KEY", "not-needed"))
        self.STT_MODEL_NAME = os.getenv("STT_MODEL_NAME", "small.en")

        if self.ENGINE == "openai" and "api.openai.com" in self.BASE_URL and self.API_KEY in ("not-needed", "local-endpoint", ""):
            self.logger.warning(
                "⚠️ Engine 'openai' targets https://api.openai.com/v1 with no API key. "
                "For a local OpenAI-compatible server, pass --base-url (e.g. http://127.0.0.1:8888/v1); "
                "for real OpenAI, pass --api-key."
            )

        self.logger.info(
            f"Config loaded: engine={self.ENGINE}, model={self.MODEL}, "
            f"port={self.PORT}, base_url={self.BASE_URL}, stt_model={self.STT_MODEL_NAME}"
        )


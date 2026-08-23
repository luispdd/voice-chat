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
    LLM engine and model configuration from environment variables.
    
    Attributes:
        ENGINE: "ollama" or "lm-studio" (default: "lm-studio")
        MODEL: Model name/tag (default: "google/gemma-3-4b-it-qat")
        PORT: Server port (default: 8000)
        HOST_IP: Local IP address
        BASE_URL: LLM API endpoint (derived from ENGINE)
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
        self.ENGINE = os.getenv("ENGINE", "lm-studio").lower()
        self.MODEL = os.getenv("MODEL", "google/gemma-3-4b-it-qat")
        self.PORT = int(os.getenv("PORT", "8000"))
        self.HOST_IP = get_local_ip()
        
        # Route base URL by engine
        if self.ENGINE == "ollama":
            self.BASE_URL = "http://localhost:11434/v1"
        else:
            self.BASE_URL = "http://localhost:1234/v1"
        
        self.logger.info(
            f"Config loaded: engine={self.ENGINE}, model={self.MODEL}, "
            f"port={self.PORT}, base_url={self.BASE_URL}"
        )

"""
LLM Client and Streaming.

Provides unified interface for LLM streaming via Ollama or LM-Studio.
Handles both native Ollama API and OpenAI-compatible endpoints.

Usage:
    from backend.common.llm import init_llm, get_chat_stream
    
    init_llm(engine="ollama", base_url="http://localhost:11434/v1")
    stream = await get_chat_stream(messages, model="llama2")
"""

import json
import httpx
from typing import Optional, AsyncGenerator
from urllib.parse import urlparse
from openai import AsyncOpenAI

# Global LLM client instance
_llm_instance: Optional[AsyncOpenAI] = None
_llm_config: dict = {}


def init_llm(
    engine: str,
    base_url: str,
    api_key: str = "local-endpoint"
) -> None:
    """
    Initialize LLM client for streaming completions.
    
    Args:
        engine: "ollama" or "lm-studio"
        base_url: API endpoint (e.g., "http://localhost:11434/v1")
        api_key: API key (default "local-endpoint" for local engines)
    """
    global _llm_instance, _llm_config
    
    _llm_config = {"engine": engine, "base_url": base_url}
    
    if engine != "ollama":
        _llm_instance = AsyncOpenAI(base_url=base_url, api_key=api_key)
    
    print(f"✅ LLM Engine Ready: [{engine.upper()}] -> {base_url}")


def _get_ollama_url(base_url: str) -> str:
    """Build native Ollama /api/chat URL from base_url."""
    parsed = urlparse(base_url)
    return f"{parsed.scheme}://{parsed.netloc}/api/chat"


async def get_chat_stream(
    history_messages: list,
    model: str,
    engine: str = None,
    base_url: str = None,
    temperature: float = 0.7,
    num_predict: int = 150
) -> AsyncGenerator:
    """
    Stream LLM completions via Ollama or OpenAI-compatible endpoint.
    
    Args:
        history_messages: Chat history with role/content
        model: Model name/tag
        engine: "ollama" or "lm-studio" (uses global if None)
        base_url: API endpoint (uses global if None)
        temperature: Sampling temperature
        num_predict: Max tokens to generate
    
    Yields:
        OpenAI-compatible completion chunks with .choices[0].delta.content
    """
    global _llm_instance, _llm_config
    
    engine = engine or _llm_config.get("engine", "lm-studio")
    base_url = base_url or _llm_config.get("base_url", "http://localhost:1234/v1")

    # PATH A: NATIVE OLLAMA API
    if engine == "ollama":
        ollama_url = _get_ollama_url(base_url)
        payload = {
            "model": model,
            "messages": history_messages,
            "stream": True,
            "think": False,  # Disable thinking/reasoning tokens
            "keep_alive": -1,  # Keep model in VRAM
            "options": {
                "num_predict": num_predict,
                "temperature": temperature
            }
        }

        async def stream_ollama_native():
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", ollama_url, json=payload) as response:
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("message", {}).get("content", "")
                                if token:
                                    # Yield OpenAI-compatible chunk structure
                                    yield type("Chunk", (), {
                                        "choices": [type("Choice", (), {
                                            "delta": type("Delta", (), {"content": token})()
                                        })()]
                                    })()
                            except Exception:
                                continue

        return stream_ollama_native()

    # PATH B: OPENAI COMPATIBLE (LM-Studio)
    else:
        if _llm_instance is None:
            _llm_instance = AsyncOpenAI(base_url=base_url, api_key="local-endpoint")

        return await _llm_instance.chat.completions.create(
            model=model,
            messages=history_messages,
            stream=True,
            temperature=temperature,
            max_tokens=num_predict
        )

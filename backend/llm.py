import json
import httpx
from urllib.parse import urlparse
from openai import AsyncOpenAI
from backend import config

llm_client = None

def init_llm():
    global llm_client
    print("📥 Initializing Async Language Model Client Interface...")
    if config.ENGINE != "ollama":
        llm_client = AsyncOpenAI(base_url=config.BASE_URL, api_key="local-endpoint")
    print(f"✅ Async LLM Engine Ready: [{config.ENGINE.upper()}] -> {config.BASE_URL}")

def _get_ollama_url() -> str:
    """Builds the native /api/chat URL using config.BASE_URL."""
    parsed = urlparse(config.BASE_URL)
    return f"{parsed.scheme}://{parsed.netloc}/api/chat"

async def get_chat_stream(history_messages: list):
    global llm_client

    # -------------------------------------------------------------------------
    # PATH A: NATIVE OLLAMA API (Strictly disables thinking mode)
    # -------------------------------------------------------------------------
    if config.ENGINE == "ollama":
        ollama_url = _get_ollama_url()
        payload = {
            "model": config.MODEL,
            "messages": history_messages,
            "stream": True,
            "think": False,   # Explicitly force disable reasoning/thinking tokens
            "keep_alive": -1, # Keep model in VRAM
            "options": {
                "num_predict": 150,
                "temperature": 0.7
            }
        }

        # Must be an inner generator function so get_chat_stream can be awaited by server.py
        async def stream_ollama_native():
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", ollama_url, json=payload) as response:
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("message", {}).get("content", "")
                                if token:
                                    # Matches the OpenAI chunk object structure server.py expects
                                    yield type("Chunk", (), {
                                        "choices": [type("Choice", (), {
                                            "delta": type("Delta", (), {"content": token})()
                                        })()]
                                    })()
                            except Exception:
                                continue

        return stream_ollama_native()

    # -------------------------------------------------------------------------
    # PATH B: STANDARD OPENAI COMPATIBLE (LM-Studio or standard endpoints)
    # -------------------------------------------------------------------------
    else:
        if llm_client is None:
            llm_client = AsyncOpenAI(base_url=config.BASE_URL, api_key="local-endpoint")

        return await llm_client.chat.completions.create(
            model=config.MODEL,
            messages=history_messages,
            stream=True
        )
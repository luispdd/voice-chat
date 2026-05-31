import logging
from openai import AsyncOpenAI
from backend import config

llm_client = None

def init_llm():
    global llm_client
    print("📥 Initializing Async Language Model Client Interface...")
    llm_client = AsyncOpenAI(base_url=config.BASE_URL, api_key="local-endpoint")
    print(f"✅ Async LLM Client Pointing to: {config.BASE_URL}")

async def get_chat_stream(history_messages: list):
    global llm_client
    
    if llm_client is None:
        print("⚠️ Warning: llm_client was None at runtime! Reinitializing...")
        llm_client = AsyncOpenAI(base_url=config.BASE_URL, api_key="local-endpoint")
        
    return await llm_client.chat.completions.create(
        model=config.MODEL,
        messages=history_messages,
        stream=True
    )
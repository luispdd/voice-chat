from openai import OpenAI
from backend import config

llm_client = None

def init_llm():
    global llm_client
    print("📥 Initializing Language Model Client Interface...")
    llm_client = OpenAI(base_url=config.BASE_URL, api_key="local-endpoint")
    print(f"✅ LLM Client Connected to Endpoint: {config.BASE_URL}")

def get_chat_stream(history_messages: list):
    global llm_client
    
    # FAIL-SAFE: If Uvicorn's reload namespace split clears out our client instance,
    # reconstruct it instantly on-demand using the active system configurations.
    if llm_client is None:
        print("⚠️ Warning: llm_client was None at runtime! Forcing emergency initialization...")
        llm_client = OpenAI(base_url=config.BASE_URL, api_key="local-endpoint")
        
    return llm_client.chat.completions.create(
        model=config.MODEL,
        messages=history_messages,
        stream=True
    )
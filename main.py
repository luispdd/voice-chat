import argparse
import os
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modular Voice Companion Application")
    
    parser.add_argument(
        "--engine",
        default=os.getenv("ENGINE", os.getenv("LLM_ENGINE", "lm-studio")),
        choices=["lm-studio", "lmstudio", "ollama", "openai", "openrouter"],
        help="Select the inference platform server component (default: lm-studio)"
    )
    parser.add_argument(
        "--model",
        default=os.getenv("MODEL", os.getenv("LLM_MODEL", None)),
        help="Exact model identifier (e.g. gpt-4o-mini, google/gemma-3-4b-it-qat, llama3)"
    )
    parser.add_argument(
        "--base-url", "--url",
        dest="base_url",
        default=os.getenv("BASE_URL", os.getenv("LLM_BASE_URL", None)),
        help="OpenAI-compatible base URL (e.g. https://api.openai.com/v1, http://127.0.0.1:8888/v1)"
    )
    parser.add_argument(
        "--api-key", "--apiKey",
        dest="api_key",
        default=os.getenv("API_KEY", os.getenv("LLM_API_KEY", None)),
        help="API key for LLM provider"
    )
    parser.add_argument(
        "--stt-model",
        dest="stt_model",
        default=os.getenv("STT_MODEL_NAME", "small.en"),
        help="Whisper.cpp ggml model name or path (default: small.en)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Web hosting channel port (default: 8000)"
    )
    
    args = parser.parse_args()

    engine = "lm-studio" if args.engine.lower() in ("lmstudio", "lm-studio") else args.engine.lower()
    base_url = args.base_url
    if not base_url:
        if engine == "ollama":
            base_url = "http://localhost:11434/v1"
        elif engine == "openai":
            base_url = "https://api.openai.com/v1"
        elif engine == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        else:
            base_url = "http://localhost:1234/v1"

    model = args.model
    if not model:
        if engine == "openai":
            model = "gpt-4o-mini"
        elif engine == "ollama":
            model = "llama3"
        elif engine == "openrouter":
            model = "meta-llama/llama-3.3-70b-instruct"
        else:
            model = "google/gemma-3-4b-it-qat"

    api_key = args.api_key or os.getenv("API_KEY", os.getenv("LLM_API_KEY", "not-needed"))

    # Pass configuration straight to the process environment
    os.environ["ENGINE"] = engine
    os.environ["MODEL"] = model
    os.environ["BASE_URL"] = base_url
    os.environ["API_KEY"] = api_key
    os.environ["STT_MODEL_NAME"] = args.stt_model
    os.environ["PORT"] = str(args.port)

    from backend import config

    uvicorn.run(
        "backend.server:app",
        host="0.0.0.0",
        port=config.PORT,
        ssl_certfile="cert.pem",
        ssl_keyfile="key.pem",
        reload=True
    )
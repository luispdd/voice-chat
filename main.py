import argparse
import uvicorn
from backend import config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modular Offline Voice Companion Application")
    
    parser.add_argument("--engine", default="lm-studio", choices=["lm-studio", "ollama"],
                        help="Select the inference platform server component (default: lm-studio)")
    parser.add_argument("--model", default="google/gemma-3-4b-it-qat",
                        help="Exact execution string name matching local model selection tag")
    parser.add_argument("--port", type=int, default=8000, help="Web hosting channel port (default: 8000)")
    
    args = parser.parse_args()

    # Seed global configurations first so the server can fetch them during initialization
    config.initialize_global_settings(engine=args.engine, model=args.model, port=args.port)

    # Pass management straight to Uvicorn worker thread
    uvicorn.run(
        "backend.server:app",
        host="0.0.0.0",
        port=config.PORT,
        ssl_certfile="cert.pem",
        ssl_keyfile="key.pem",
        reload=True
    )
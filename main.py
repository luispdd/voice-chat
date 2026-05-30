import argparse
import uvicorn
from backend import config, stt, llm, tts

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modular Offline Voice Companion Application")
    
    # Configure custom parameters
    parser.add_argument("--engine", default="lm-studio", choices=["lm-studio", "ollama"],
                        help="Select the inference platform server component (default: lm-studio)")
    parser.add_argument("--model", default="google/gemma-3-4b-it-qat",
                        help="Exact execution string name matching local model selection tag")
    parser.add_argument("--port", type=int, default=8000, help="Web hosting channel port (default: 8000)")
    
    args = parser.parse_args()

    # 1. Seed global variables and settings
    config.initialize_global_settings(engine=args.engine, model=args.model, port=args.port)

    print("\n" + "="*60)
    print("🔥 BOOTING SYSTEM COMPONENTS...")
    print("="*60)
    
    # 2. Warm up individual neural layers
    stt.init_stt()
    tts.init_tts()
    llm.init_llm()
    
    print("\n" + "="*60)
    print("🚀 OFFLINE VOICE COMPANION ACTIVE AND WARMED UP")
    print("="*60)
    print(f"🏠 Web Console App URL:      https://127.0.0.1:{config.PORT}")
    print(f"📱 Local Area Network URL:   https://{config.HOST_IP}:{config.PORT}")
    print(f"🧠 Selected Model Target:    [{config.ENGINE.upper()}] -> {config.MODEL}")
    print("="*60 + "\n")

    # 3. Pass application package layout mapping over to Uvicorn worker thread
    uvicorn.run(
        "backend.server:app",
        host="0.0.0.0",
        port=config.PORT,
        ssl_certfile="cert.pem",
        ssl_keyfile="key.pem",
        reload=True
    )
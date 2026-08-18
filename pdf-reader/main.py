import argparse
import os
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF Voice Reader Application")
    
    parser.add_argument("--engine", default="lm-studio", choices=["lm-studio", "ollama"],
                        help="Select the inference platform server component (default: lm-studio)")
    parser.add_argument("--model", default="llama2",
                        help="Exact execution string name matching local model selection tag")
    parser.add_argument("--port", type=int, default=8000, help="Web hosting channel port (default: 8000)")
    
    args = parser.parse_args()

    # Pass configuration straight to the process environment
    os.environ["ENGINE"] = args.engine
    os.environ["MODEL"] = args.model
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

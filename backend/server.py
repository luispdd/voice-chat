import os
import uuid
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import config, stt, llm, tts

# 1. Define the Lifespan Context Manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*60)
    print("🔥 FASTAPI LIFESPAN: INITIALIZING CHANNELS INDEPENDENTLY...")
    print("="*60)
    
    # Force loading directly inside the running active app thread
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
    
    yield  # The server handles web requests while hanging here
    
    print("🛑 Shutting down server engines...")

# 2. Inject the lifespan handler into the FastAPI app shell
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

sessions = {}

@app.get("/")
def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    html_content = html_content.replace("__HOST_IP__", config.HOST_IP).replace("__PORT__", str(config.PORT))
    return HTMLResponse(content=html_content)

@app.post("/chat")
async def chat_endpoint(request: Request, file: UploadFile = File(...)):
    client_ip = request.client.host
    if client_ip not in sessions:
        sessions[client_ip] = [{"role": "system", "content": config.SYSTEM_INSTRUCTIONS}]
    
    device_history = sessions[client_ip]
    audio_payload_bytes = await file.read()
    
    user_text = stt.transcribe_voice_bytes(audio_payload_bytes)
    
    if not user_text:
        async def empty_gen():
            yield b"TEXT:USER:[Silence detected]\n"
            yield b"TEXT:AI_TOKEN:I didn't catch that. Please try speaking clearly again.\n"
        return StreamingResponse(empty_gen(), media_type="application/octet-stream")

    print(f"👤 [{client_ip}] Said: {user_text}")
    device_history.append({"role": "user", "content": user_text})

    if len(device_history) > 11:
        print(f"🧹 Pruning conversation context window for client session: [{client_ip}]")
        device_history = [device_history[0]] + device_history[-10:]
        sessions[client_ip] = device_history

    async def audio_stream_generator():
        try:
            yield f"TEXT:USER:{user_text}\n".encode('utf-8')

            response_stream = await llm.get_chat_stream(device_history)
            text_buffer = ""
            full_ai_response = ""

            async for chunk in response_stream:
                token = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ""
                if token:
                    text_buffer += token
                    full_ai_response += token

                    safe_token = token.replace('\n', ' ')
                    yield f"TEXT:AI_TOKEN:{safe_token}\n".encode('utf-8')

                    sentences = re.split(r'(?<=[.!?])\s+', text_buffer)
                    while len(sentences) > 1:
                        completed_sentence = sentences.pop(0).strip()
                        text_buffer = " ".join(sentences)
                        
                        if completed_sentence:
                            yield tts.generate_speech_bytes(completed_sentence)

            remaining_text = text_buffer.strip()
            if remaining_text:
                yield tts.generate_speech_bytes(remaining_text)

            device_history.append({"role": "assistant", "content": full_ai_response})
            print(f"🤖 [AI to {client_ip}]: {full_ai_response}")

        except Exception as e:
            print(f"🚨 Async Audio Stream Generator Exception: {e}")

    return StreamingResponse(audio_stream_generator(), media_type="application/octet-stream")
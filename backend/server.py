import os
import re
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import config, stt, llm, tts
from backend.config import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("="*60)
    logger.info("🔥 FASTAPI LIFESPAN: INITIALIZING CHANNELS INDEPENDENTLY...")
    logger.info("="*60)
    
    stt.init_stt()  # Initializes Whisper (STT)
    tts.init_tts()  # Initializes Piper (TTS)
    llm.init_llm()  # Initializes LLM client
    
    logger.info("="*60)
    logger.info("🚀 OFFLINE VOICE COMPANION ACTIVE AND WARMED UP")
    logger.info("="*60)
    
    yield
    logger.info("🛑 Shutting down server engines...")

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
    req_start_time = time.perf_counter()
    client_ip = request.client.host
    logger.info(f"📥 [{client_ip}] Incoming audio payload received...")

    if client_ip not in sessions:
        sessions[client_ip] = [{"role": "system", "content": config.SYSTEM_INSTRUCTIONS}]
    
    device_history = sessions[client_ip]
    audio_payload_bytes = await file.read()
    
    # STEP 1: STT Transcription Profiling
    stt_start = time.perf_counter()
    user_text = stt.transcribe_voice_bytes(audio_payload_bytes)
    stt_duration = time.perf_counter() - stt_start
    logger.info(f"⏱️ [STT Duration]: {stt_duration:.2f}s")
    
    if not user_text:
        logger.info("⚠️ [STT]: Silence or unreadable audio detected.")
        async def empty_gen():
            yield b"TEXT:USER:[Silence detected]\n"
            yield b"TEXT:AI_TOKEN:I didn't catch that. Please try speaking clearly again.\n"
        return StreamingResponse(empty_gen(), media_type="application/octet-stream")

    logger.info(f"👤 [{client_ip}] Said: \"{user_text}\"")
    device_history.append({"role": "user", "content": user_text})

    if len(device_history) > 11:
        logger.info(f"🧹 Pruning conversation context window for [{client_ip}]")
        device_history = [device_history[0]] + device_history[-10:]
        sessions[client_ip] = device_history

    async def audio_stream_generator():
        try:
            yield f"TEXT:USER:{user_text}\n".encode('utf-8')

            # STEP 2: LLM Connection & First Token Profiling
            llm_request_start = time.perf_counter()
            logger.info("⏳ Sending request to LLM engine...")
            
            response_stream = await llm.get_chat_stream(device_history)
            
            first_token_received = False
            text_buffer = ""
            full_ai_response = ""

            async for chunk in response_stream:
                token = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ""
                if token:
                    if not first_token_received:
                        ttft = time.perf_counter() - llm_request_start
                        logger.info(f"⚡ [LLM Time-To-First-Token (TTFT)]: {ttft:.2f}s")
                        first_token_received = True

                    text_buffer += token
                    full_ai_response += token

                    safe_token = token.replace('\n', ' ')
                    yield f"TEXT:AI_TOKEN:{safe_token}\n".encode('utf-8')

                    # STEP 3: Sentence TTS Profiling
                    sentences = re.split(r'(?<=[.!?])\s+', text_buffer)
                    while len(sentences) > 1:
                        completed_sentence = sentences.pop(0).strip()
                        text_buffer = " ".join(sentences)
                        
                        if completed_sentence:
                            tts_start = time.perf_counter()
                            logger.info(f"🔊 Synthesizing TTS for: \"{completed_sentence}\"")
                            speech_bytes = tts.generate_speech_bytes(completed_sentence)
                            tts_duration = time.perf_counter() - tts_start
                            logger.info(f"⏱️ [TTS Duration]: {tts_duration:.2f}s")
                            yield speech_bytes

            remaining_text = text_buffer.strip()
            if remaining_text:
                tts_start = time.perf_counter()
                logger.info(f"🔊 Synthesizing remaining TTS for: \"{remaining_text}\"")
                speech_bytes = tts.generate_speech_bytes(remaining_text)
                logger.info(f"⏱️ [TTS Duration]: {time.perf_counter() - tts_start:.2f}s")
                yield speech_bytes

            device_history.append({"role": "assistant", "content": full_ai_response})
            total_duration = time.perf_counter() - req_start_time
            logger.info(f"🤖 [AI Response Completed in {total_duration:.2f}s]: \"{full_ai_response}\"")

        except Exception as e:
            logger.error(f"🚨 Async Audio Stream Generator Exception: {e}")

    return StreamingResponse(audio_stream_generator(), media_type="application/octet-stream")
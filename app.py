import os
import json
import wave
import shutil
import uuid
import subprocess
import re
import socket
import numpy as np
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
import onnxruntime as ort
from piper.voice import PiperVoice
from piper.config import PiperConfig
import moonshine_onnx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

print("📥 Initializing Moonshine ONNX Transformer Engine...")
stt_model = moonshine_onnx.MoonshineOnnxModel(model_name="moonshine/tiny")
print("✅ Moonshine ONNX Engine Online.")

print("📥 Initializing Piper TTS Engine...")
model_path = os.path.join("voice_models", "en_US-amy-medium.onnx")
sess_opt = ort.SessionOptions()
sess_opt.intra_op_num_threads = 2
sess_opt.inter_op_num_threads = 2
session = ort.InferenceSession(model_path, sess_opt, providers=["CPUExecutionProvider"])

with open(model_path + ".json", "r", encoding="utf-8") as f:
    config_dict = json.load(f)
voice = PiperVoice(config=PiperConfig.from_dict(config_dict), session=session)
print("✅ Piper TTS Engine Online.")

# --- PROACTIVE NEURAL ENGINE WARM-UP ---
print("🔥 Warming up neural network engines...")
try:
    # Force an initial transcription memory allocation check if supported
    if hasattr(stt_model, 'warmup'):
        stt_model.warmup()
    
    # Run a dummy voice pass through Piper to prime the ONNX inference threads in RAM
    for _ in voice.synthesize("System online"):
        pass
    print("⚡ All models pre-loaded and fully warmed up in RAM!")
except Exception as e:
    print(f"⚠️ Warmup routine notification: {e}")

SYSTEM_INSTRUCTIONS = (
    "You are a helpful, brief web voice assistant. Keep answers short and conversational. "
    "Do not use bullet points, asterisks, or special markdown characters."
)

sessions = {}

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    return local_ip

HOST_IP = get_local_ip()
PORT = 8000

@app.on_event("startup")
async def print_startup_banner():
    print("\n" + "="*60)
    print("🚀 OFFLINE VOICE COMPANION SERVER INITIALIZED")
    print("="*60)
    print(f"🏠 Access from THIS machine:  https://127.0.0.1:{PORT}")
    print(f"📱 Access from OTHER devices: https://{HOST_IP}:{PORT}")
    print("="*60 + "\n")

@app.get("/")
def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    html_content = html_content.replace("__HOST_IP__", HOST_IP).replace("__PORT__", str(PORT))
    return HTMLResponse(content=html_content)

@app.post("/chat")
async def chat_endpoint(request: Request, file: UploadFile = File(...)):
    client_ip = request.client.host
    if client_ip not in sessions:
        sessions[client_ip] = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]
    
    device_history = sessions[client_ip]
    request_id = str(uuid.uuid4())
    temp_raw_input = f"raw_received_{request_id}"
    temp_wav_output = f"user_voice_{request_id}.wav"
    
    with open(temp_raw_input, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    user_text = ""
    try:
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", temp_raw_input,
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            temp_wav_output
        ]
        subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        transcription_list = moonshine_onnx.transcribe(temp_wav_output, stt_model)
        user_text = transcription_list[0].strip() if transcription_list else ""
    except Exception as e:
        print(f"🚨 Moonshine Processing Exception: {e}")
    finally:
        if os.path.exists(temp_raw_input): os.remove(temp_raw_input)
        if os.path.exists(temp_wav_output): os.remove(temp_wav_output)

    if not user_text:
        def empty_gen():
            yield b"TEXT:USER:[Silence detected]\n"
            yield b"TEXT:AI_TOKEN:I didn't catch that. Please try speaking clearly again.\n"
        return StreamingResponse(empty_gen(), media_type="application/octet-stream")

    print(f"👤 [{client_ip}] Said: {user_text}")
    device_history.append({"role": "user", "content": user_text})

    def audio_stream_generator():
        try:
            # Yield user text first to display it immediately on response startup
            yield f"TEXT:USER:{user_text}\n".encode('utf-8')

            response_stream = client.chat.completions.create(
                model="google/gemma-3-4b-it-qat",
                messages=device_history,
                stream=True
            )

            text_buffer = ""
            full_ai_response = ""

            for chunk in response_stream:
                token = chunk.choices[0].delta.content
                if token:
                    text_buffer += token
                    full_ai_response += token

                    # Safely escape text tokens to protect packet boundaries
                    safe_token = token.replace('\n', ' ')
                    yield f"TEXT:AI_TOKEN:{safe_token}\n".encode('utf-8')

                    sentences = re.split(r'(?<=[.!?])\s+', text_buffer)
                    while len(sentences) > 1:
                        completed_sentence = sentences.pop(0).strip()
                        text_buffer = " ".join(sentences)
                        
                        if completed_sentence:
                            for audio_chunk in voice.synthesize(completed_sentence):
                                raw_bytes = audio_chunk.audio_int16_bytes
                                length_prefix = len(raw_bytes).to_bytes(4, byteorder='big')
                                yield b"AUDIO:" + length_prefix + raw_bytes

            remaining_text = text_buffer.strip()
            if remaining_text:
                for audio_chunk in voice.synthesize(remaining_text):
                    raw_bytes = audio_chunk.audio_int16_bytes
                    length_prefix = len(raw_bytes).to_bytes(4, byteorder='big')
                    yield b"AUDIO:" + length_prefix + raw_bytes

            device_history.append({"role": "assistant", "content": full_ai_response})
            print(f"🤖 [AI to {client_ip}]: {full_ai_response}")

        except Exception as e:
            print(f"🚨 Audio Stream Generator Exception: {e}")

    return StreamingResponse(audio_stream_generator(), media_type="application/octet-stream")
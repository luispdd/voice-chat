import os
import json
import wave
import shutil
import base64
import socket
import uuid
import subprocess
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
import onnxruntime as ort
from piper.voice import PiperVoice
from piper.config import PiperConfig

# Lightweight, platform-agnostic Moonshine ONNX speech engine
import moonshine_onnx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder for separated style.css and app.js
app.mount("/static", StaticFiles(directory="static"), name="static")

# Connection client mapping back to your local LM Studio instance
client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

print("📥 Initializing Moonshine ONNX Transformer Engine...")
# Instantiates model weights matrix locally at startup
stt_model = moonshine_onnx.MoonshineOnnxModel(model_name="moonshine/tiny")
print("✅ Moonshine ONNX Engine Online.")

SYSTEM_INSTRUCTIONS = (
    "You are a helpful, brief web voice assistant. Keep answers short and conversational. "
    "Do not use bullet points or special markdown characters."
)

# Active user profile sessions mapped by incoming device IP addresses
sessions = {}

# --- LOCAL NETWORK DYNAMIC RESOLVER ---
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Pings Google DNS to find out which local network adapter interface is active
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
def startup_banner():
    print("\n" + "="*60)
    print("🚀 MULTI-DEVICE OFFLINE VOICE BOT SERVICE ACTIVE")
    print(f"🏠 Local Host Access:     https://localhost:{PORT}")
    print(f"🌐 LAN Remote Network Access: https://{HOST_IP}:{PORT}")
    print("="*60 + "\n")

@app.get("/")
def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    # Dynamic substitution to wire up remote mobile devices to the exact host adapter IP
    html_content = html_content.replace("__HOST_IP__", HOST_IP).replace("__PORT__", str(PORT))
    return HTMLResponse(content=html_content)

@app.post("/chat")
async def chat_endpoint(request: Request, file: UploadFile = File(...)):
    # Isolate session conversation context data structure using the device IP
    client_ip = request.client.host
    if client_ip not in sessions:
        sessions[client_ip] = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]
    
    device_history = sessions[client_ip]

    request_id = str(uuid.uuid4())
    temp_raw_input = f"raw_received_{request_id}"
    temp_wav_output = f"user_voice_{request_id}.wav"
    output_audio_path = f"ai_response_{request_id}.wav"
    
    with open(temp_raw_input, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    user_text = ""
    try:
        # 1. Transcode compressed payload from browsers (ogg, webm, mp4) into raw WAV PCM
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", temp_raw_input,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            temp_wav_output
        ]
        subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 2. Extract speech tokens via Moonshine ONNX engine block
        transcription_list = moonshine_onnx.transcribe(temp_wav_output, stt_model)
        user_text = transcription_list[0].strip() if transcription_list else ""

    except Exception as e:
        print(f"🚨 Moonshine Speech-To-Text processing fault: {e}")
        user_text = ""
    finally:
        if os.path.exists(temp_raw_input): os.remove(temp_raw_input)
        if os.path.exists(temp_wav_output): os.remove(temp_wav_output)

    if not user_text:
        return JSONResponse(content={
            "user_text": "[Silence detected]", 
            "ai_text": "I didn't catch that. Please try speaking clearly again.", 
            "audio_base64": ""
        })
        
    print(f"👤 [{client_ip}] Said: {user_text}")
    
    # Order of Operations fix: update conversation history array BEFORE querying local LLM
    device_history.append({"role": "user", "content": user_text})
    
    try:
        response = client.chat.completions.create(
            model="google/gemma-3-4b-it-qat",
            messages=device_history,
            stream=False
        )
        ai_text_response = response.choices[0].message.content
    except Exception as e:
        print(f"🚨 Local LLM Engine Exception: {e}")
        ai_text_response = "I had a hitch processing that request."
        
    device_history.append({"role": "assistant", "content": ai_text_response})
    print(f"🤖 [AI to {client_ip}]: {ai_text_response}")
    
    # Initialize Piper TTS Framework
    model_path = os.path.join("voice_models", "en_US-amy-medium.onnx")
    sess_opt = ort.SessionOptions()
    sess_opt.intra_op_num_threads = 2
    sess_opt.inter_op_num_threads = 2
    session = ort.InferenceSession(model_path, sess_opt, providers=["CPUExecutionProvider"])
    
    with open(model_path + ".json", "r", encoding="utf-8") as f:
        config_dict = json.load(f)
    voice = PiperVoice(config=PiperConfig.from_dict(config_dict), session=session)
    
    with wave.open(output_audio_path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(voice.config.sample_rate)
        for chunk in voice.synthesize(ai_text_response):
            wav_file.writeframes(chunk.audio_int16_bytes)

    with open(output_audio_path, "rb") as audio_file:
        audio_encoded = base64.b64encode(audio_file.read()).decode('utf-8')

    if os.path.exists(output_audio_path):
        os.remove(output_audio_path)

    return JSONResponse(content={
        "user_text": user_text,
        "ai_text": ai_text_response,
        "audio_base64": audio_encoded
    })
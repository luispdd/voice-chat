import os
import shutil
import uuid
import re
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import config, stt, llm, tts

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file asset hosting
app.mount("/static", StaticFiles(directory="static"), name="static")

sessions = {}

@app.get("/")
def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    # Populate index placeholders with current network profiles
    html_content = html_content.replace("__HOST_IP__", config.HOST_IP).replace("__PORT__", str(config.PORT))
    return HTMLResponse(content=html_content)

@app.post("/chat")
async def chat_endpoint(request: Request, file: UploadFile = File(...)):
    client_ip = request.client.host
    if client_ip not in sessions:
        sessions[client_ip] = [{"role": "system", "content": config.SYSTEM_INSTRUCTIONS}]
    
    device_history = sessions[client_ip]
    request_id = str(uuid.uuid4())
    temp_raw_input = f"raw_received_{request_id}"
    temp_wav_output = f"user_voice_{request_id}.wav"
    
    with open(temp_raw_input, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    user_text = stt.transcribe_voice_bytes(temp_raw_input, temp_wav_output)
    
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
            yield f"TEXT:USER:{user_text}\n".encode('utf-8')

            response_stream = llm.get_chat_stream(device_history)
            text_buffer = ""
            full_ai_response = ""

            for chunk in response_stream:
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
            print(f"🚨 Audio Stream Generator Exception: {e}")

    return StreamingResponse(audio_stream_generator(), media_type="application/octet-stream")
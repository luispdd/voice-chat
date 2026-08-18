import io
import os
import re
import numpy as np
import soundfile as sf
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader
from typing import Optional
from contextlib import asynccontextmanager

from backend import config
from backend.common import tts, llm

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize TTS (starts Piper engine)
    tts.init_tts()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def get_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/read-pdf")
async def read_pdf(
    file: UploadFile = File(...),
    start_page: int = Form(0),
    llm_engine: str = Form("None"),
    llm_model: str = Form("llama2")
):
    # 1. Extract text from PDF
    pdf_bytes = await file.read()
    reader = PdfReader(io.BytesIO(pdf_bytes))
    
    extracted_text = ""
    start_idx = max(0, start_page - 1) # User input is 1-indexed, pypdf is 0-indexed
    for page_num in range(start_idx, len(reader.pages)):
        page = reader.pages[page_num]
        text = page.extract_text()
        if text:
            extracted_text += text + "\n"
            
    # Limit text length for initial test to avoid long processing
    extracted_text = extracted_text[:2000].strip()

    if not extracted_text:
        return Response(content="No text found in PDF.", media_type="text/plain", status_code=400)

    # 2. Optional LLM Processing
    final_text = extracted_text
    if llm_engine != "None" and llm_engine.lower() != "none":
        # Initialize LLM with default or selected engine
        base_url = "http://localhost:11434/v1" if llm_engine == "ollama" else "http://localhost:1234/v1"
        llm.init_llm(engine=llm_engine, base_url=base_url)
        
        prompt = f"Please summarize or clean up the following text for narration:\n\n{extracted_text}"
        messages = [{"role": "user", "content": prompt}]
        
        response_stream = await llm.get_chat_stream(messages, model=llm_model, num_predict=1000)
        
        llm_text = ""
        async for chunk in response_stream:
            token = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ""
            llm_text += token
            
        final_text = llm_text.strip() if llm_text.strip() else extracted_text

    # 3. Text to Speech
    raw_pcm_chunks = []
    
    sentences = re.split(r'(?<=[.!?])\s+', final_text)
    for sentence in sentences:
        if not sentence.strip():
            continue
        for audio_chunk in tts._tts_instance.synthesize(sentence):
            raw_pcm_chunks.append(np.frombuffer(audio_chunk.audio_int16_bytes, dtype=np.int16))

    if not raw_pcm_chunks:
        return Response(content="Failed to generate audio.", status_code=500)

    audio_data = np.concatenate(raw_pcm_chunks)
    sample_rate = tts._tts_instance.config.sample_rate

    wav_io = io.BytesIO()
    sf.write(wav_io, audio_data, sample_rate, format='WAV', subtype='PCM_16')
    wav_io.seek(0)
    
    return Response(
        content=wav_io.read(), 
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=narration.wav"}
    )

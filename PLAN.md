Below is a clean “migration-ready” package you can paste into your logged-in chat later.

---

# 🧠 Project Summary (Voice Chat Bot)

You are building a **voice-driven AI chat bot application** with:

* Project management NX
* Frontend: Angular 22
* UI Library: PrimeNG
* Backend: FastAPI
* Database: MongoDB
* Deployment: Docker + Docker Compose

## Core concept

A web application where users:

1. Speak via microphone using the browser technologies to manage the microphone (voice input)
2. Audio is transcribed to text
3. Backend processes input (LLM + optional RAG)
4. Response is generated as text
5. Response is converted to speech (TTS)
6. User hears the bot reply

## Key features

* Real-time voice chat interface
* Speech-to-text (STT)
* Text-to-speech (TTS)
* Chat memory per session/user
* RAG-based knowledge retrieval (MongoDB vectors)
* Chat history persistence

---

# 🏗️ Architecture Notes

## 1. Frontend (Angular)

### Responsibilities

* Capture microphone input
* Stream audio or send chunks
* Display chat UI
* Play TTS audio responses
* Manage session state

### Tech

* Angular 22 (standalone components)
* PrimeNG for UI components
* Web Audio API / MediaRecorder API

### Key modules

```text
/chat
  - voice input component
  - chat history component
  - audio playback service

/core
  - API service (FastAPI calls)
  - session service

/shared
  - models (message, session, user)
```

---

## 2. Backend (FastAPI)

### Responsibilities

* Receive audio/text input
* Handle STT (speech-to-text)
* Call LLM
* Handle RAG retrieval
* Generate TTS audio
* Manage chat sessions
* Store/retrieve data from MongoDB

### Core pipeline

```text
Audio → STT → Text → RAG retrieval → LLM → Response text → TTS → Audio
```

### Suggested services

* `stt_service` (Whisper or equivalent)
* `llm_service` (OpenAI / local model)
* `rag_service`
* `tts_service`
* `chat_service`

---

## 3. Database (MongoDB)

### Collections

#### users

```json
{
  "_id": "...",
  "email": "...",
  "created_at": "..."
}
```

#### sessions

```json
{
  "_id": "...",
  "user_id": "...",
  "created_at": "...",
  "last_active": "..."
}
```

#### messages

```json
{
  "session_id": "...",
  "role": "user | assistant",
  "text": "...",
  "timestamp": "...",
  "audio_url": "optional"
}
```

#### documents (RAG source data)

```json
{
  "title": "...",
  "content": "...",
  "chunks": [
    {
      "text": "...",
      "embedding": [0.12, 0.98, ...],
      "metadata": {}
    }
  ]
}
```

---

## 4. RAG System (MongoDB-based)

### Flow

1. User asks question
2. Convert query → embedding
3. MongoDB vector search over chunks
4. Retrieve top-K chunks
5. Inject into LLM prompt
6. Generate response

### Why MongoDB works here

* stores embeddings directly
* supports vector search indexes
* stores raw + structured data together
* reduces infra complexity

---

## 5. Docker Setup

```text
frontend (Angular + Nginx)
backend (FastAPI + Uvicorn)
mongodb
```

Optional later:

* redis (session caching)
* worker service (background embeddings)

---

# 📋 TODO Roadmap

## Phase 0 — Setup

* [ ] Create repo structure (frontend/backend)
* [ ] Setup Angular 22 project
* [ ] Setup FastAPI project
* [ ] Add Docker Compose baseline
* [ ] Add MongoDB container

---

## Phase 1 — Basic Chat (Text Only MVP)

* [ ] Angular chat UI (text input/output)
* [ ] FastAPI `/chat` endpoint
* [ ] MongoDB message storage
* [ ] Session management
* [ ] Basic API integration

✔ Goal: working text chatbot

---

## Phase 2 — Voice Input (STT)

* [ ] Add microphone capture in Angular
* [ ] Send audio to backend
* [ ] Integrate STT (e.g. Whisper)
* [ ] Return transcribed text to chat flow

✔ Goal: voice → text → chat works

---

## Phase 3 — Voice Output (TTS)

* [ ] Integrate TTS service in backend
* [ ] Return audio response URL or stream
* [ ] Angular audio playback component
* [ ] Auto-play bot responses

✔ Goal: full voice loop

---

## Phase 4 — RAG System

* [ ] Document ingestion pipeline
* [ ] Chunking strategy
* [ ] Generate embeddings
* [ ] Store in MongoDB
* [ ] Vector search integration
* [ ] Inject context into LLM prompt

✔ Goal: knowledge-aware bot

---

## Phase 5 — Conversation Memory

* [ ] Session-based memory
* [ ] Summarization of long chats (optional)
* [ ] Context window management

---

## Phase 6 — Polish

* [ ] Streaming responses (optional)
* [ ] UI improvements (PrimeNG chat UX)
* [ ] Loading indicators
* [ ] Error handling
* [ ] Rate limiting

---

## Phase 7 — Deployment

* [ ] Docker Compose production config
* [ ] Environment variables setup
* [ ] Reverse proxy (optional Nginx)
* [ ] Persistent MongoDB volume
* [ ] Basic CI/CD (optional)

---

# 🚀 Key Design Decision Summary

* Frontend: Angular SPA (no SSR needed)
* Backend: FastAPI (stateless API)
* DB: MongoDB (documents + vectors + chat memory)
* Architecture: simple 3-service Docker setup
* AI layer: STT + LLM + TTS pipeline
* RAG: MongoDB vector search

---

If you want next step help, I can also generate:

* Docker Compose file
* FastAPI project skeleton
* Angular voice chat component structure
* or a clean RAG implementation plan (chunking + embeddings + prompts)

# Monorepo Project Plan: Voice & Text Companion

This document outlines the phased milestone roadmap for converting the voice assistant into a polyglot monorepo managed by Nx, Bun, and uv.

---

# Architecture Stack Overview

- Workspace Orchestrator: Nx
- Frontend: Angular 22 (PrimeNG, Web Audio API / MediaRecorder API)
- Frontend Engine / Package Manager: Bun / bunx
- Backend Framework: FastAPI
- Python Virtual Environment & Dependency Manager: uv
- Speech & LLM Engines: Faster-Whisper (STT), Piper (TTS), Native Ollama API
- Database & Vector Search: MongoDB (Deferred to Milestone 4)
- Deployment & Isolation: Docker + Docker Compose
- Testing: Playwright / Cypress (E2E) + Pytest

---

# Workspace Structure Target

voice-chat/                       <-- Nx Monorepo Root
├── nx.json                       <-- Workspace pipeline & caching rules
├── package.json                  <-- Root dependencies & Bun lock configuration
├── bun.lock                      <-- Bun Lockfile
├── pyproject.toml                <-- Root uv workspace file
├── uv.lock                       <-- Unified Python lockfile
├── docker-compose.yml            <-- Infra orchestration (App, Database, Engines)
│
├── apps/
│   ├── frontend/                 <-- Angular 22 App (Managed via Bun)
│   │   ├── project.json          <-- Nx target definitions (build, serve, lint)
│   │   └── src/
│   │
│   ├── frontend-e2e/             <-- E2E Testing Suite (Playwright or Cypress)
│   │   ├── project.json          <-- Nx target dependsOn: ["frontend:serve", "backend:serve"]
│   │   └── src/
│   │
│   └── backend/                  <-- FastAPI Application (Managed via uv)
│       ├── project.json          <-- Nx targets delegating to `uv run`
│       ├── pyproject.toml
│       └── backend/              <-- STT, TTS, Native Ollama stream modules
│
└── libs/                         <-- Shared types and schema definitions

---

# Milestone Roadmap

## Milestone 1: Monorepo Migration & Feature Parity (In-Memory MVP)

**Objective:** Establish the Nx polyglot workspace and achieve exact feature parity with the current working setup without requiring a database.

### Workspace Scaffolding
- [ ] Initialize root Nx workspace configuration (`nx.json`, `package.json`, `bun.lock`).
- [ ] Configure `uv` workspace root (`pyproject.toml`, `uv.lock`).
- [ ] Generate `apps/frontend` using Angular 22 and configure Bun package management.
- [ ] Scaffold `apps/backend` for FastAPI managed via `uv`.
- [ ] Configure Nx target delegations in `apps/backend/project.json` for `uv run python main.py`.

### Backend Migration
- [ ] Port existing FastAPI application logic into `apps/backend`.
- [ ] Preserve Faster-Whisper (STT) audio decoding logic.
- [ ] Preserve Native Ollama API streaming integration (`think: False` parameter).
- [ ] Preserve Piper (TTS) audio synthesis with Markdown and Emoji stripping function.
- [ ] Keep session memory in-memory using Python dictionary session buffers.

### Frontend Migration & Dual-Input Support
- [ ] Install and configure PrimeNG UI components in Angular 22.
- [ ] Build Angular chat UI supporting both text field input and microphone toggle button.
- [ ] Implement audio recording service using browser MediaRecorder API.
- [ ] Implement chunked audio playback service for streaming responses.

**Completion Criteria:** You can type a message or speak into the Angular UI and receive real-time transcribed audio responses from the backend without errors.

---

## Milestone 2: E2E Testing Infrastructure

**Objective:** Verify application stability and build flow reliability using automated End-to-End test orchestrations.

- [ ] Generate `apps/frontend-e2e` using Nx Playwright or Cypress generator.
- [ ] Configure target dependencies in `apps/frontend-e2e/project.json` so `e2e` depends on `frontend:serve` and `backend:serve`.
- [ ] Write initial E2E tests covering:
  - Text input submission and response rendering verification.
  - Basic DOM elements and connection state assertions.
  - Server health check verification.

**Completion Criteria:** Running `bunx nx e2e frontend-e2e` automatically boots backend and frontend servers, executes tests, and reports passing results.

---

## Milestone 3: Containerization & Docker Orchestration

**Objective:** Containerize the application for consistent execution and deployment environments across machines.

- [ ] Create `Dockerfile` for `apps/frontend` (Multi-stage build: Bun build -> Nginx static host).
- [ ] Create `Dockerfile` for `apps/backend` (uv environment + System dependencies for Whisper/Piper).
- [ ] Create base `docker-compose.yml` orchestrating `frontend` and `backend` services.
- [ ] Add Nx targets in `apps/backend` and `apps/frontend` to build and launch Docker containers (`bunx nx run-many -t docker-up`).

**Completion Criteria:** Running `docker-compose up` or Nx docker targets boots the complete app stack cleanly from a fresh environment.

---

## Milestone 4: Database Integration & Session Persistence

**Objective:** Replace in-memory dictionaries with MongoDB to store user chats and persistent session histories.

- [ ] Add MongoDB service to `docker-compose.yml` with persistent volume storage.
- [ ] Create backend database connector using `motor` or `pymongo`.
- [ ] Implement MongoDB schemas for `sessions` and `messages`.
- [ ] Update backend service to write and retrieve chat history from MongoDB collections.
- [ ] Update Angular UI to display past chat sessions retrieved from MongoDB endpoints.

**Completion Criteria:** Restarting the backend server preserves all previous conversation sessions in the UI.

---

## Milestone 5: Knowledge Retrieval (RAG via MongoDB Vector Search)

**Objective:** Enhance assistant capabilities by allowing document ingestion and context retrieval.

- [ ] Enable MongoDB Vector Search capabilities on the database cluster/container.
- [ ] Build backend document ingestion CLI script to chunk documents and generate vector embeddings.
- [ ] Implement embedding search function in backend before invoking LLM generation.
- [ ] Update native Ollama API payload to inject retrieved document chunks into prompt context.

**Completion Criteria:** Asking specific questions about ingested documents yields accurate context-grounded answers from the assistant.

---

## Milestone 6: Advanced Frontend Architecture (Module Federation)

**Objective:** Refactor the frontend application to practice Angular Microfrontend design using Module Federation.

- [ ] Configure `@nx/angular:module-federation` for `apps/frontend`.
- [ ] Extract the Chat Interface into a federated remote module.
- [ ] Establish host application container that dynamically loads chat remotes.
- [ ] Validate shared state management across microfrontend boundaries.

**Completion Criteria:** The chat module loads dynamically as an independent federated bundle without disrupting current voice and audio capabilities.
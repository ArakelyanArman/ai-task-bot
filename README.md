# AI Task Bot — Omni-Channel Task Management System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.159-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.31-2CA5E0?logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Google GenAI](https://img.shields.io/badge/Google_GenAI-Gemini-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
[![Docker Compose](https://img.shields.io/badge/Docker_Compose-Enabled-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)

A production-ready, omni-channel task management system developed for the **AI Engineering Intern Technical Assessment**. 

Users capture tasks via Telegram through text or voice messages. Voice inputs are processed asynchronously using Gemini Audio Transcription through a distributed worker queue, providing real-time feedback to Telegram and streaming live updates to a responsive web Kanban dashboard over WebSockets.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [How to Obtain API Keys](#how-to-obtain-api-keys)
  - [1. Gemini API Key](#1-gemini-api-key)
  - [2. Telegram Bot Token](#2-telegram-bot-token)
- [Quick Start with Docker Compose](#quick-start-with-docker-compose)
- [Configuration Reference](#configuration-reference)
- [Local Development Setup](#local-development-setup)
- [Technical Assessment Compliance Matrix](#technical-assessment-compliance-matrix)
- [Resilience, Queue Workflow & UX Design](#resilience-queue-workflow--ux-design)
- [API & WebSocket Specification](#api--websocket-specification)
- [Project Directory Structure](#project-directory-structure)

---

## System Architecture

```
                                  +-----------------------------+
                                  |     Telegram User           |
                                  +--------------+--------------+
                                                 |
                                     (Text or Voice Message)
                                                 |
                                                 v
+-----------------------+           +------------+--------------+
|   React Dashboard     |           |     aiogram Bot Poller    |
|   (Vite + Nginx)      |           +------------+--------------+
+-----------+-----------+                        |
            |                                    | 1. Store task (status: processing)
            | WebSocket                          | 2. Enqueue transcription job
            v                                    v
+-----------+-----------+           +------------+--------------+
|   FastAPI API / WS    |           |   Redis (Broker & PubSub) |
+-----------+-----------+           +------------+--------------+
            ^                                    |
            | Pub/Sub Events                     | Job Queue (ARQ)
            |                                    v
+-----------+-----------+           +------------+--------------+
|   PostgreSQL 16 DB    |<----------+     ARQ Worker Service    |
+-----------------------+           +------------+--------------+
                                                 |
                                                 | Audio payload
                                                 v
                                    +------------+--------------+
                                    |    Google Gemini GenAI    |
                                    |  (Audio Transcription)    |
                                    +---------------------------+
```

### Flow Breakdown
1. **Quick Capture**: A user sends a text or voice message to the Telegram Bot.
   - **Text**: Stored immediately in PostgreSQL; event published to Redis Pub/Sub; task cards populate on the dashboard in real time.
   - **Voice**: The bot performs instant pre-validation (length/size limits), replies with immediate visual feedback (`🎙 Transcribing…`), writes a pending task record to PostgreSQL, and enqueues an asynchronous job into the Redis queue via **ARQ**.
2. **Asynchronous Processing**: The dedicated worker service downloads the voice file from the Telegram API, forwards the audio buffer to Gemini for transcription, updates the database, updates the original Telegram message with the transcribed task text, and publishes a real-time event.
3. **Live Dashboard Sync**: The FastAPI service listens to the Redis Pub/Sub channel and broadcasts `task.created`, `task.updated`, and `task.deleted` messages across connected client WebSockets.

---

## Tech Stack

| Layer | Technologies | Role / Justification |
| :--- | :--- | :--- |
| **Telegram Interface** | Python 3.12, `aiogram` 3 | Asynchronous Telegram Bot API framework for high-throughput messaging. |
| **Backend API** | FastAPI, Pydantic v2, Uvicorn | Async REST API & native WebSocket endpoints. |
| **Database & ORM** | PostgreSQL 16, SQLAlchemy 2 (asyncpg), Alembic | Fully async relational storage with migrations. |
| **Queue & Broker** | Redis 7, ARQ | Lightweight async task queue with exponential backoff and pub/sub. |
| **AI Transcription** | `google-genai` (Gemini Audio) | Cloud-native speech-to-text with format resilience (`audio/ogg`). |
| **Web Dashboard** | React 19, Vite, CSS Modules | Responsive Kanban board with real-time WebSocket state management. |
| **Reverse Proxy & Serving**| Nginx (Alpine) | Production static file server with API/WS reverse proxying. |
| **Containerization** | Docker, Docker Compose | Multi-stage, multi-container orchestration. |

---

## How to Obtain API Keys

### 1. Gemini API Key
Evaluators can obtain a free Gemini API key using Google AI Studio:

1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Sign in with any Google account.
3. Click **"Create API key"** (or select an existing Google Cloud project).
4. Copy the generated key string (format: `AIzaSy...`).
5. Assign this key to `GEMINI_API_KEY` in your `.env` file.

### 2. Telegram Bot Token
To connect the bot to Telegram:

1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to choose a bot name and username.
3. Copy the HTTP API token provided by BotFather (format: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
4. Assign this token to `TELEGRAM_BOT_TOKEN` in your `.env` file.

---

## Quick Start with Docker Compose

The entire stack is containerized and orchestrated through `docker-compose.yml`.

### Step 1: Clone and Configure Environment

```bash
git clone <repository-url>
cd ai-task-bot

# Copy sample environment configuration
cp .env.example .env
```

Edit `.env` and fill in your keys:

```ini
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### Step 2: Launch All Services

```bash
docker compose up --build
```

Docker Compose launches and manages six synchronized services:
- `postgres`: Persistent database with health check.
- `redis`: In-memory broker and cache with health check.
- `migrate`: Runs Alembic database schema migrations before dependent services start.
- `api`: FastAPI application serving REST endpoints and WebSockets on port `8000`.
- `worker`: ARQ background worker processing audio transcription jobs.
- `bot`: Telegram bot polling process.
- `frontend`: React Kanban dashboard served on port `8080`.

### Step 3: Access the Application

- **Web Dashboard**: [http://localhost:8080](http://localhost:8080)
- **API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Endpoint**: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **Telegram Bot**: Start chatting with your registered bot on Telegram.

---

## Configuration Reference

The application reads configuration from environment variables defined in `.env` (validated by `pydantic-settings`):

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Yes | — | Authentication token from @BotFather. |
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API key. |
| `GEMINI_TRANSCRIBE_MODEL` | No | `gemini-3.5-transcribe` | Gemini transcription model ID. |
| `MAX_AUDIO_DURATION` | No | `60` | Maximum audio length accepted by bot (in seconds). |
| `MAX_AUDIO_SIZE` | No | `10485760` (10MB) | Maximum audio payload accepted by bot (in bytes). |
| `POSTGRES_USER` | No | `postgres` | PostgreSQL username. |
| `POSTGRES_PASSWORD` | No | `postgres` | PostgreSQL password. |
| `POSTGRES_DB` | No | `taskbot` | Database name. |
| `DATABASE_URL` | No | Docker internal URI | Async SQLAlchemy connection string (`asyncpg`). |
| `REDIS_URL` | No | Docker internal URI | Redis broker and Pub/Sub connection URI. |
| `FRONTEND_PORT` | No | `8080` | Host port mapped to the web dashboard. |

---

## Local Development Setup

For running components locally without Docker:

### 1. Prerequisites
- Python 3.12+
- Node.js 20+
- Local PostgreSQL (`localhost:5432`)
- Local Redis (`localhost:6379`)

### 2. Backend & Worker Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run migrations
cd backend
alembic upgrade head
cd ..

# Run FastAPI API (Terminal 1)
uvicorn app.main:app --app-dir backend --reload --port 8000

# Run ARQ Worker (Terminal 2)
PYTHONPATH=backend arq app.worker.settings.WorkerSettings

# Run Telegram Bot (Terminal 3)
PYTHONPATH=backend python -m app.bot.main
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs at [http://localhost:5173](http://localhost:5173).

---

## Technical Assessment Compliance Matrix

| Assessment Requirement | Implementation Details |
| :--- | :--- |
| **Telegram Bot API** | Integrated using `aiogram 3`. Provides `/start`, `/help`, and direct message capture. |
| **Text Task Entry** | Immediate parsing, DB persistence, and Redis Pub/Sub broadcast to web dashboard. |
| **Voice Task Entry** | Handles voice notes, downloads raw Telegram audio, validates size/duration constraints, and delegates transcription asynchronously. |
| **Speech-to-Text** | Integrates Google Gemini audio transcription client with smart format handling. |
| **PostgreSQL Persistence**| Asynchronous SQLAlchemy models (`users`, `tasks`) with Alembic migration version control. |
| **Redis Broker / Queue** | ARQ distributed worker queue for async audio jobs and Redis Pub/Sub channel for live updates. |
| **Web Dashboard** | React 19 single-page app featuring a 3-column Kanban board (`Pending`, `In Progress`, `Completed`). |
| **Real-time Synchronization** | WebSocket connection streaming backend state mutations live with zero page reloads. |
| **Status Toggles** | Forward/backward status advancement directly on task cards synced via PATCH requests. |
| **Docker Orchestration** | Complete `docker-compose.yml` with health checks, build caching, and dependencies ordering. |

---

## Resilience, Queue Workflow & UX Design

### 1. Instant Feedback UX
Voice messages often take a few seconds to process over external AI APIs. To provide responsive feedback:
- The Telegram bot instantly responds with `🎙 Transcribing…`.
- A task card appears immediately on the Kanban board with a live spinning loader and "Transcribing…" badge.
- When transcription completes, the bot edits the original message into `✅ Task created: <transcription>`, and the Kanban card transitions from loading to the full text title automatically.

### 2. Audio Validation & Guardrails
- Reject oversized voice notes (>10MB) or lengthy recordings (>60s) directly at the Telegram handler to prevent resource exhaustion.
- Enforces strict character and duration limits.

### 3. Queue Resilience & Error Handling
- **Transient Failures (Rate limits / HTTP 5xx / Network timeouts)**:
  ARQ job retries with **exponential backoff** (`5s * 2^(retry_count - 1)`).
- **Terminal Failures**:
  If retries are exhausted or invalid audio is encountered, the worker marks the task status as `FAILED`, persists the diagnostic error message in PostgreSQL, and alerts the frontend via WebSocket so the user sees the failure reason on the card.

---

## API & WebSocket Specification

### REST Endpoints

- `GET /api/health` — Checks database and Redis connectivity.
- `GET /api/tasks` — List all tasks (optional query filter: `?status=pending|in_progress|completed`).
- `POST /api/tasks` — Create a new task manually.
- `PATCH /api/tasks/{task_id}` — Update task status or title.
- `DELETE /api/tasks/{task_id}` — Remove a task.

### WebSocket Endpoint

- `WS /api/ws` — Real-time event stream. Clients receive JSON payloads:
  - `{"type": "task.created", "task": { ... }}`
  - `{"type": "task.updated", "task": { ... }}`
  - `{"type": "task.deleted", "task": { ... }}`

---

## Project Directory Structure

```
ai-task-bot/
├── .env.example              # Environment variables template
├── docker-compose.yml        # Multi-service container orchestration
├── backend/
│   ├── Dockerfile            # Python backend container definition
│   ├── requirements.txt      # Python dependencies
│   ├── alembic.ini           # Migration settings
│   ├── alembic/              # Database migration scripts
│   └── app/
│       ├── main.py           # FastAPI application entrypoint
│       ├── api/              # REST routes & WebSocket handler
│       ├── bot/              # aiogram Telegram bot dispatcher & handlers
│       ├── core/             # Pydantic configuration & settings
│       ├── db/               # Async SQLAlchemy engine & session factory
│       ├── models/           # SQLAlchemy ORM models (Task, User, Enums)
│       ├── repositories/     # Data access layer (TaskRepository, UserRepository)
│       ├── schemas/          # Pydantic validation schemas
│       ├── services/         # Gemini transcription, Redis events, Telegram client
│       └── worker/           # ARQ worker task definitions & queue configuration
└── frontend/
    ├── Dockerfile            # Multi-stage Nginx container build
    ├── nginx.conf            # Nginx reverse proxy configuration
    ├── package.json          # Node dependencies
    ├── vite.config.js        # Vite build configuration
    └── src/
        ├── App.jsx           # Main Kanban board application component
        ├── api.js            # Axios/Fetch API client
        ├── useTasks.js       # Real-time WebSocket + REST task state hook
        └── styles.css        # Dashboard styling & layout
```

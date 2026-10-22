# AI Task Bot: 3-Day Implementation Plan (FastAPI + Gemini)

> Create tasks via Telegram (text or voice), see them live on a web dashboard.
> Tick tasks off by changing `- [ ]` to `- [x]`.

---

## 1. Architecture

```
Telegram ──► Bot service ──► Postgres
                │                ▲
                │ enqueue        │
                ▼                │
             Redis queue ──► Worker (Gemini transcription)
                                 │ publish event (after DB commit)
                                 ▼
                           Redis pub/sub ──► API (FastAPI) ──WebSocket──► React dashboard
```

| Layer | Choice |
|---|---|
| Bot | `aiogram` 3.x (long polling) |
| API | FastAPI + SQLAlchemy 2 (async) + Alembic |
| Queue | `arq` |
| Transcription | Gemini API (`google-genai`), model `gemini-3.5-transcribe`, `SMART` mode |
| Frontend | React + Vite + Tailwind, served by nginx |
| Infra | Docker Compose |

One backend codebase and image, three entrypoints:

| Service | Command |
|---|---|
| `api` | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| `worker` | `arq app.worker.settings.WorkerSettings` |
| `bot` | `python -m app.bot.main` |

### Voice message flow

1. Bot receives the voice message and **immediately** replies "🎙 Transcribing…".
2. Bot creates a task (`source=voice`, `transcription_status=processing`, placeholder title), publishes `task.created`, and enqueues `transcribe_task`.
3. Worker downloads the audio from Telegram, sends it to Gemini, updates the task, and commits.
4. Worker publishes `task.updated`. The API pushes it over WebSocket to the dashboard.
5. Worker edits the "Transcribing…" message to "✅ Task created: <text>".

On failure after retries: `transcription_status=failed`, `error_message` stored, and the user gets "Couldn't transcribe, please try again or type it".

Text messages skip the queue for transcription: create the task, publish the event, reply.

### Gemini transcription sketch (`services/transcription.py`)

```python
from google import genai
from google.genai import types

client = genai.Client()  # reads GEMINI_API_KEY

async def transcribe(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    response = await client.aio.models.generate_content(
        model=settings.gemini_transcribe_model,
        contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)],
        config=types.GenerateContentConfig(
            audio_transcription_config=types.AudioTranscriptionConfig(
                mode="SMART",
                language_codes=[],   # auto-detect
            )
        ),
    )
    return (response.text or "").strip()
```

If sending bytes inline fails, switch to `client.files.upload(...)` (the documented path) and delete the upload afterwards.

---

## 2. Progress So Far

### Setup
- [x] Repo and folder layout
- [x] Telegram bot created, token saved
- [x] Gemini API key
- [x] Virtualenv and `requirements.txt`
- [x] `core/config.py` with pydantic-settings
- [x] `.env.example` and `.gitignore`
- [ ] `ruff` config (5 minutes, run it once before submitting)
- [ ] README skeleton (fill in on Day 3)

### Database
- [x] Postgres and Redis running locally via Compose
- [x] Async engine and session factory
- [x] `User` and `Task` models
- [x] Alembic initialized, first migration generated and applied, tables verified
- [x] Pydantic schemas (`TaskCreate`, `TaskUpdate`, `TaskRead`)

---

## 3. Day 1: Backend, Bot, and Voice Pipeline

**Goal by end of day:** send a voice note to the bot and see the transcribed task in Postgres.

### Morning: REST API and text bot (~3 h)

- [x] Tasks repository (create, list with optional status filter, get, update status, delete)
- [x] User repository: get-or-create by `telegram_id`
- [x] `GET /api/tasks` (with `status` filter)
- [x] `POST /api/tasks`
- [x] `PATCH /api/tasks/{id}` (status change)
- [x] `DELETE /api/tasks/{id}`
- [x] `GET /api/health` (checks DB and Redis)
- [x] CORS middleware
- [x] 404 on a missing id, 422 on invalid input
- [x] Bot entrypoint with aiogram long polling
- [x] `/start` and `/help`
- [x] Text handler: get-or-create user, create task (`source=text`), reply with confirmation
- [x] Politely reject unsupported message types (photos, stickers, and so on)
- [x] Manual check: send a text message and see the row in Postgres

### Afternoon: Gemini and the worker (~5 h)

**Gemini spike (time-box to 30 minutes)**
- [ ] Record a voice note in Telegram, download the `.ogg`, and transcribe it with a standalone script using `SMART` mode
- [ ] Test one voice note with a self-correction ("buy milk, no, oat milk") and one in Armenian or Russian

**Queue and voice handler**
- [x] arq `WorkerSettings` (Redis settings, `max_tries`, `job_timeout`) and a helper to enqueue jobs
- [x] Voice handler: reject over the duration/size limit, send "🎙 Transcribing…", store its `message_id`, create the task, enqueue `transcribe_task(task_id, file_id)`

**Transcription job**
- [x] `services/telegram.py`: get the file and download the audio
- [x] `services/transcription.py`: the Gemini wrapper with a timeout
- [x] `transcribe_task`: download, transcribe, update title, set `transcription_status=done`, edit the bot message with the result

**Resilience (build this in now, not later)**
- [x] Timeouts on Telegram download and Gemini call
- [x] Retries with exponential backoff for transient errors (timeouts, 5xx, 429)
- [x] No retry for permanent errors (bad audio, bad key)
- [x] Handle empty or blocked transcripts explicitly
- [x] On final failure: set `failed`, store `error_message`, notify the user in Telegram
- [x] Idempotency: skip the job if the task is already `done`
- [ ] Clean up temp files (and any uploaded files) in a `finally` block
- [ ] Log the task id on every log line

**Tests (keep it to the valuable ones)**
- [ ] API: create a task, change status, 404 on a missing id
- [ ] Worker: mocked Gemini client covering success, failure, and empty transcript

---

## 4. Day 2: Real-Time Layer and Dashboard

**Goal by end of day:** send a message to the bot and watch a card appear and move on the dashboard without refreshing.

### Morning: real-time backend (~2.5 h)

- [ ] Event schema: `{ "type": "task.created" | "task.updated" | "task.deleted", "task": {...} }`
- [ ] `services/events.py`: `publish_event()` using Redis pub/sub
- [ ] Call `publish_event()` after commit from the REST endpoints, the bot, and the worker
- [ ] API lifespan: background task subscribing to the Redis channel
- [ ] Connection manager for WebSocket clients
- [ ] `GET /ws` endpoint, handle disconnects
- [ ] Broadcast Redis events to all connected clients
- [ ] Milestone: connect with `websocat` or the browser console, send a Telegram message, and see the event arrive

### Daytime: dashboard (~5.5 h)

- [ ] Scaffold React with Vite, add Tailwind
- [ ] API client module and a typed `Task` model
- [ ] Fetch tasks on load via `GET /api/tasks`
- [ ] Kanban board with three columns: Pending, In Progress, Completed
- [ ] Task card (title, 🎙/⌨️ source icon, created time)
- [ ] Status buttons on each card (move to previous/next column) that call `PATCH`
- [ ] WebSocket hook: merge `task.created`, `task.updated`, `task.deleted` into state
- [ ] Reconnect on disconnect, and refetch tasks after reconnecting
- [ ] "Transcribing…" spinner on voice tasks that are still processing
- [ ] Failed state showing the error message
- [ ] Responsive layout (columns stack on mobile)

### End of day: start Docker early (~1 h)

- [ ] `backend/Dockerfile` and `.dockerignore` (shared by `api`, `worker`, `bot`)
- [ ] Add `api` and `worker` to `docker-compose.yml` and confirm they run in containers

---

## 5. Day 3: Docker, Fresh-Clone Test, and README

**Goal by end of day:** a stranger can clone the repo, add their keys, and run one command.

### Morning: containerize everything (~3 h)

- [ ] Add `bot` service to Compose
- [ ] `frontend/Dockerfile` (multi-stage: build, then nginx)
- [ ] `nginx.conf` proxying `/api` and `/ws` (with WebSocket upgrade headers) to the API
- [ ] Add the `frontend` service
- [ ] `depends_on: condition: service_healthy` for `api`, `bot`, and `worker`
- [ ] Container-specific URLs in Compose (`postgres` and `redis` as hosts, not `localhost`)
- [ ] Entrypoint that runs `alembic upgrade head` before starting the API
- [ ] Secrets passed via `.env`, never baked into images

### Midday: verify (~2 h)

- [ ] Clone to a fresh folder, copy `.env.example` to `.env`, add keys, run `docker compose up --build`
- [ ] Walk through the full flow: text message, voice message, status toggle, two browser tabs staying in sync
- [ ] Test a failure: stop the worker or use an invalid Gemini key and confirm the failed state shows in Telegram and on the dashboard
- [ ] Fix whatever broke (budget time for this, something always does)

### Afternoon: documentation and submission (~2.5 h)

- [ ] README: overview and architecture diagram
- [ ] README: setup steps (how to get the Telegram token and Gemini key) and env var table
- [ ] README: design decisions (why FastAPI, arq, pub/sub, Gemini `SMART` mode)
- [ ] README: known limitations (for example no dashboard authentication, polling instead of webhooks) and what you would build next
- [ ] 1–2 minute demo video or GIF: voice message in, dashboard updates live
- [ ] Remove dead code and debug prints
- [ ] Confirm no secrets in git (including history)
- [ ] Run `ruff` and the tests one last time
- [ ] Submit

---

## 6. Cut Line (if time runs short)

Protect these, in order: the voice pipeline with resilience, live dashboard updates, `docker compose up` working from a fresh clone, and the README. If you must drop something, drop it in this order:

1. Responsive polish and the empty-state messages
2. The Kanban layout (a plain list grouped by status with buttons still meets the requirement)
3. The second test (keep the mocked worker test)

---

## 7. Mapping to the Evaluation Criteria

| Criterion | How this plan addresses it |
|---|---|
| **Code quality** | Layered structure (routers, services, repositories), typed schemas, env-based config, model name in config, `ruff` |
| **Resilience** | Timeouts, retries with backoff, 429 handling, no retries on permanent errors, size/duration limits, explicit failed state, idempotent job, cleanup in `finally` |
| **Redis workflow** | Redis as the arq job queue and as the pub/sub event bus, documented flow |
| **UX / speed** | Instant "Transcribing…" reply, card visible immediately in a processing state, message edited in place with the result, `SMART` mode for clean titles |

---

## 8. Pitfalls to Avoid

- Blocking the bot handler with transcription. Always enqueue and return fast.
- Publishing events before the DB commit, which makes the dashboard fetch stale data.
- Using `localhost` inside containers. Use Compose service names.
- Forgetting the WebSocket upgrade headers in `nginx.conf`.
- No timeout on the Gemini call.
- Hardcoding the Gemini model name.
- Mixing sync and async code. Stay async everywhere and use `client.aio` for Gemini.
- Committing `.env` or any API key.

---

## 9. Definition of Done

- [ ] A text message in Telegram creates a task that appears on the dashboard within about a second, without refreshing
- [ ] A voice message gets an instant acknowledgement, then the transcript, and the dashboard updates live
- [ ] A failed transcription gives the user a clear message and the task shows a failed state
- [ ] Status changes persist and sync across open browser tabs
- [ ] `docker compose up --build` from a fresh clone brings up the whole system
- [ ] README is complete and the demo is recorded

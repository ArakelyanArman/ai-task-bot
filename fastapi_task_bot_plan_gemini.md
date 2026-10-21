# AI Task Bot: Implementation Plan (FastAPI + Gemini Edition)

> Omni-channel task management: create tasks via Telegram (text or voice), see them live on a web dashboard.
> Voice is transcribed with the **Gemini API**.

---

## 1. Architecture

```
Telegram ──► Bot service ──► Postgres (tasks, users)
                │                 ▲
                │ enqueue         │
                ▼                 │
             Redis queue ──► Worker (Gemini transcription, notifications)
                                  │ publish event (after DB commit)
                                  ▼
                            Redis pub/sub ──► API (FastAPI) ──WebSocket──► React dashboard
```

### Stack

| Layer | Choice | Notes |
|---|---|---|
| Bot | `aiogram` 3.x | Async, well documented |
| API | FastAPI + SQLAlchemy 2 (async) + Alembic | Typed, built-in WebSockets, auto docs at `/docs` |
| Queue | `arq` | Async-native Redis queue, lightweight |
| Transcription | **Gemini API** via the `google-genai` SDK, model `gemini-3.5-transcribe` | Dedicated speech-to-text model, accepts OGG/Opus (Telegram's voice format) |
| Frontend | React + Vite + Tailwind | Served by nginx in production |
| Infra | Docker Compose | Required by the brief |

### Why Gemini works well here

- **Dedicated transcription model.** `gemini-3.5-transcribe` is built for speech-to-text, not general chat.
- **Telegram format supported.** Telegram voice notes are OGG/Opus, and the model lists `audio/ogg` and `audio/opus` among supported formats, so no conversion step with ffmpeg is needed (still verify this with a real voice note).
- **Automatic language detection** across 85+ locales, including code-switching. No configuration is needed if users speak different languages.
- **`SMART` mode** removes filler words and resolves spoken self-corrections. For example, "Buy milk, uh, actually no, oat milk" becomes a clean task title instead of a messy raw transcript. This is ideal for task titles.
- **Same API key can later power extras** (for example, extracting due dates or priority from the text) with no new vendor.

### Voice message flow

1. Bot receives the voice message and **immediately** replies "🎙 Transcribing…" (UX criterion).
2. Bot creates a task row (`source=voice`, `transcription_status=processing`) and enqueues `transcribe_task`.
3. Dashboard shows the card instantly in a "transcribing" state (event is published on creation).
4. Worker downloads the audio from Telegram, sends it to Gemini, updates the task.
5. Worker publishes `task.updated` on Redis pub/sub, and the API pushes it over WebSocket.
6. Worker edits the "Transcribing…" message to "✅ Task created: <text>".

Text messages skip transcription: create the task, publish the event, reply.

### Data model

**users**
- `id`, `telegram_id` (unique), `username`, `created_at`

**tasks**
- `id`, `user_id` (FK), `title`, `description` (nullable)
- `status`: `pending` | `in_progress` | `completed`
- `source`: `text` | `voice`
- `transcription_status`: `none` | `processing` | `done` | `failed`
- `error_message` (nullable)
- `telegram_chat_id`, `telegram_message_id`
- `created_at`, `updated_at`

### Suggested project layout

```
ai-task-bot/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan, routers
│   │   ├── core/                # config.py (pydantic-settings), logging.py
│   │   ├── db/                  # session.py, base.py
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── repositories/        # DB access (tasks, users)
│   │   ├── api/                 # routers: tasks.py, health.py, ws.py
│   │   ├── services/            # transcription.py (Gemini), telegram.py, events.py
│   │   ├── bot/                 # main.py, handlers.py
│   │   └── worker/              # settings.py (arq), jobs.py
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

One backend codebase and image, three entrypoints:

| Service | Command |
|---|---|
| `api` | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| `worker` | `arq app.worker.settings.WorkerSettings` |
| `bot` | `python -m app.bot.main` |

### Gemini transcription: sketch of `services/transcription.py`

```python
from google import genai
from google.genai import types

client = genai.Client()  # reads GEMINI_API_KEY from the environment

async def transcribe(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    response = await client.aio.models.generate_content(
        model=settings.gemini_transcribe_model,   # "gemini-3.5-transcribe", kept in env/config
        contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)],
        config=types.GenerateContentConfig(
            audio_transcription_config=types.AudioTranscriptionConfig(
                mode="SMART",          # removes fillers, resolves self-corrections
                language_codes=[],     # empty = auto-detect language
            )
        ),
    )
    return (response.text or "").strip()
```

Notes:
- The official docs show the **Files API** path: `client.files.upload(file=...)` then pass the returned file in `contents`. Sending the bytes inline (as above) avoids an extra upload round trip and may be faster for short voice notes. **Test both** and keep whichever works reliably. If you use the Files API, delete the uploaded file afterwards.
- Keep the **model name in config** (`GEMINI_TRANSCRIBE_MODEL`), since Gemini model names change over time.
- Google's docs currently label `generate_content` as "Legacy" and promote a newer Interactions API. The transcription page still documents `generate_content`, which is the simplest path. Check the docs when you start, in case this has changed.
- `SMART` mode cannot be combined with word timestamps or speaker diarization. You don't need those here.
- Standard requests support audio up to 1 hour, but cap voice notes at something like 60 seconds in your own code. Tasks should be short.
- Real-time streaming transcription exists (`gemini-3.5-transcribe-live` via the Live API), but you don't need it. Voice notes arrive as complete files.

---

## 2. Task Checklist

### Phase 0: Setup (~0.5 day)

- [ ] Create the repo and the folder layout above
- [ ] Create the Telegram bot via @BotFather and save the token
- [ ] Get a Gemini API key from Google AI Studio (https://aistudio.google.com/apikey)
- [ ] Create a Python virtualenv and `requirements.txt` (fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, aiogram, arq, redis, httpx, **google-genai**, pytest, pytest-asyncio)
- [ ] Write `core/config.py` using `pydantic-settings` (DB URL, Redis URL, bot token, `GEMINI_API_KEY`, `GEMINI_TRANSCRIBE_MODEL`, voice duration/size limits)
- [ ] Write `.env.example` (no real secrets) and a `.gitignore` that excludes `.env`
- [ ] Set up linting/formatting (`ruff`, `eslint`/`prettier`)
- [ ] Add a README skeleton

### Phase 1: Database and REST API (~1 day)

- [ ] Run Postgres and Redis locally (a minimal compose file is fine for now)
- [ ] Write the async SQLAlchemy engine and session factory (`db/session.py`)
- [ ] Define `User` and `Task` models (use Enums for status/source/transcription_status)
- [ ] Initialize Alembic (async template) and generate the first migration
- [ ] Apply the migration and verify the tables exist
- [ ] Write Pydantic schemas: `TaskCreate`, `TaskUpdate`, `TaskRead`
- [ ] Write the tasks repository (create, list, get, update status, delete)
- [ ] `GET /api/tasks` with optional `status` filter
- [ ] `POST /api/tasks`
- [ ] `PATCH /api/tasks/{id}` (status change, validate allowed values)
- [ ] `DELETE /api/tasks/{id}`
- [ ] `GET /api/health` (checks DB and Redis)
- [ ] Add CORS middleware
- [ ] Return proper 404/422 errors
- [ ] Tests: create a task, list with filter, change status, 404 on a missing id

### Phase 2: Telegram Bot, Text (~0.5 day)

- [ ] Bot entrypoint (`bot/main.py`) with aiogram long polling
- [ ] `/start` handler (welcome and usage hint)
- [ ] `/help` handler
- [ ] Get-or-create `User` by `telegram_id` on every incoming message
- [ ] Text handler: create a `Task` (`source=text`) and reply with a confirmation
- [ ] Ignore or reject empty messages and unsupported message types politely
- [ ] Optional: `/list` command showing the user's pending tasks
- [ ] Manual test: send a text message and check the row in Postgres

### Phase 3: Redis Queue, Worker and Gemini Transcription (~1.5 days, core of the evaluation)

**Gemini spike (do this first, before wiring the queue)**
- [ ] Record a short voice note in Telegram, download the `.ogg` file manually, and run a standalone script that transcribes it with `gemini-3.5-transcribe`
- [ ] Compare inline bytes vs Files API for speed and reliability, and decide which to use
- [ ] Compare `VERBATIM` vs `SMART` mode on a few messages (include one with a self-correction) and confirm `SMART` gives good task titles
- [ ] Test an Armenian or Russian voice note to confirm language auto-detection works for your users

**Queue setup**
- [ ] Configure `arq` `WorkerSettings` (Redis settings, functions, `max_tries`, `job_timeout`)
- [ ] Create a shared helper for enqueueing jobs from the bot/API
- [ ] Start the worker locally and run a dummy job end to end

**Voice handler in the bot**
- [ ] Voice message handler
- [ ] Reject files over the size/duration limit with a friendly message
- [ ] Send the instant "🎙 Transcribing…" reply and store its `message_id`
- [ ] Create the task (`source=voice`, `transcription_status=processing`)
- [ ] Enqueue `transcribe_task(task_id, file_id)`

**Transcription job**
- [ ] Write `services/telegram.py`: get file path and download the audio (in memory or a temp file)
- [ ] Write `services/transcription.py`: the Gemini wrapper with a timeout
- [ ] `transcribe_task` job: download, transcribe, update title, set `transcription_status=done`
- [ ] Edit the original bot message with the transcript ("✅ Task created: …")
- [ ] Publish a `task.updated` event after the DB commit

**Second workflow (shows the queue is used for more than one thing)**
- [ ] `send_notification` job (for example failure notices or confirmations)

**Resilience**
- [ ] Timeouts on every external call (Telegram download, Gemini)
- [ ] Retries with exponential backoff (3 attempts) for transient errors (timeouts, 5xx)
- [ ] Handle Gemini rate limiting (HTTP 429) specifically: back off and retry rather than failing immediately
- [ ] Do not retry permanent errors (invalid audio, bad API key). Fail fast instead
- [ ] Handle empty responses, blocked responses, and silent audio (no text returned) explicitly
- [ ] On final failure: set `transcription_status=failed`, store `error_message`, notify the user ("Couldn't transcribe, please try again or type it")
- [ ] Idempotency: skip if the task is already `done`, so retries don't duplicate work
- [ ] Always delete temp audio files (and any Files API uploads) in a `finally` block
- [ ] Structured logging with the task id in every log line
- [ ] Tests: mock the Gemini client to simulate success, timeout, 429, and empty transcript

### Phase 4: Real-Time Layer (~0.5 day)

- [ ] Define the event schema: `{ "type": "task.created" | "task.updated" | "task.deleted", "task": {...} }`
- [ ] Write `services/events.py`: `publish_event()` using Redis pub/sub
- [ ] Call `publish_event()` from the REST endpoints, the bot, and the worker (always after commit)
- [ ] In the API lifespan, start a background task that subscribes to the Redis channel
- [ ] Connection manager class for active WebSocket clients
- [ ] `GET /ws` WebSocket endpoint that registers the client and handles disconnects
- [ ] Broadcast incoming Redis events to all connected clients
- [ ] Milestone test: connect with a WebSocket client (`websocat` or the browser console), create a task via Telegram, and see the event arrive

### Phase 5: Dashboard (~1.5 days)

**Setup**
- [ ] Scaffold React with Vite
- [ ] Add Tailwind
- [ ] Create an API client module and a typed `Task` model

**Core UI**
- [ ] Fetch tasks on load via `GET /api/tasks`
- [ ] Kanban board with three columns: Pending, In Progress, Completed
- [ ] Task card component (title, source icon 🎙/⌨️, created time)
- [ ] Status toggle on each card (buttons for the next/previous status)
- [ ] `PATCH` call on toggle with optimistic update and rollback on error

**Real-time**
- [ ] WebSocket hook that connects to `/ws`
- [ ] Merge `task.created`, `task.updated`, and `task.deleted` events into state
- [ ] Auto-reconnect with backoff, and refetch tasks after reconnecting
- [ ] Connection status indicator ("Live" / "Reconnecting…")

**UX details**
- [ ] "Transcribing…" spinner state on voice tasks
- [ ] Failed state with the error message
- [ ] Empty-state message for columns with no tasks
- [ ] Responsive layout (columns stack on mobile)
- [ ] Optional: drag-and-drop between columns

### Phase 6: Docker and DevOps (~0.5–1 day)

- [ ] `backend/Dockerfile` (shared by `api`, `worker`, `bot`)
- [ ] `frontend/Dockerfile` (multi-stage: build, then serve with nginx)
- [ ] `nginx.conf` proxying `/api` and `/ws` (with WebSocket upgrade headers) to the API
- [ ] `docker-compose.yml` with services: `frontend`, `api`, `bot`, `worker`, `postgres`, `redis`
- [ ] Healthchecks for `postgres` and `redis`
- [ ] `depends_on: condition: service_healthy` for api, bot, and worker
- [ ] Named volume for Postgres data
- [ ] Entrypoint script that runs `alembic upgrade head` before starting the API
- [ ] Use service names (`postgres`, `redis`) in connection strings, never `localhost`
- [ ] Pass all secrets (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, DB password) via `.env`
- [ ] Test: clone to a fresh folder, copy `.env.example` to `.env`, run `docker compose up --build`, and confirm everything works end to end

### Phase 7: Polish and Submission (~0.5 day)

- [ ] README: overview and architecture diagram
- [ ] README: setup steps (including how to get the Telegram token and Gemini API key) and env var table
- [ ] README: design decisions (why FastAPI, why arq, why pub/sub, why Gemini)
- [ ] README: known limitations (for example no dashboard auth) and future improvements
- [ ] Record a 1–2 minute demo (voice message in, dashboard updates live)
- [ ] Remove dead code and debug prints
- [ ] Confirm no secrets are committed (check git history too)
- [ ] Run linters and tests one last time
- [ ] Submit

---

## 3. Mapping to the Evaluation Criteria

| Criterion | How this plan addresses it |
|---|---|
| **Code quality** | Layered structure (routers, services, repositories), typed schemas, env-based config, model name in config, linting |
| **Resilience** | Timeouts, retries with backoff, 429 handling, no retries on permanent errors, size/duration limits, explicit failed state, idempotent jobs, user-facing error messages, temp-file cleanup |
| **Redis workflow** | Redis as queue (`arq`) and as event bus (pub/sub), two job types, documented flow |
| **UX / speed** | Instant "Transcribing…" reply, card visible immediately in a transcribing state, message edited in place with the result, `SMART` mode for clean titles |

---

## 4. Common Pitfalls

- **Blocking the bot handler** with transcription. Always enqueue and return fast.
- **Publishing events before the DB commit**, which makes the dashboard see stale data.
- **Using `localhost` inside containers.** Use compose service names.
- **Forgetting WebSocket upgrade headers** in the nginx config.
- **No timeout on the Gemini call**, which can hang a worker forever.
- **Ignoring rate limits.** Free-tier Gemini keys have request limits, so handle 429 with backoff.
- **Hardcoding the model name.** Gemini model names change, so keep it in config.
- **Leaving temp audio files (or Files API uploads) behind.**
- **Mixing sync and async DB code.** Stay fully async with SQLAlchemy 2 + asyncpg. Use the async Gemini client (`client.aio`) inside async jobs.
- **Committing your API keys.** Keep `.env` out of git and rotate any key that leaks.
- **No dashboard auth.** Not required by the brief, but mention it as a known limitation in the README.

---

## 5. Stretch Goals (only if everything above is done)

- [ ] Extract due date / priority from the task text with a Gemini structured-output call (same API key)
- [ ] Fallback model: if `gemini-3.5-transcribe` fails, retry once with a general Gemini model using audio understanding
- [ ] Inline keyboard buttons in the bot to change task status
- [ ] Dashboard login scoped to the user's tasks (for example the Telegram Login Widget)
- [ ] Integration tests with testcontainers
- [ ] Task search and filter on the dashboard

---

## 6. Definition of Done

- [ ] A text message in Telegram creates a task that appears on the dashboard within about a second, without refreshing
- [ ] A voice message gets an instant acknowledgement, then the transcript, and the dashboard updates live
- [ ] A failed transcription gives the user a clear message and the task shows a failed state
- [ ] Status toggles (Pending, In Progress, Completed) persist and sync across open browser tabs
- [ ] `docker compose up --build` from a fresh clone brings up the whole system
- [ ] README is complete and the demo is recorded

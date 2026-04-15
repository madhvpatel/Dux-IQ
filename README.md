# Dux IQ

Dux IQ is a merchant intelligence and operations copilot for payment businesses.
It combines:

- a FastAPI backend for merchant analytics, chat, proactive cards, action workflows, and POS/dispute utilities
- a domain-agent layer for settlements, transactions, disputes, terminals, and growth questions
- an Expo / React Native frontend under `IQ/frontend`
- a bank and merchant knowledge base under `bank_kb/` and `agent/`

The current primary backend is the root FastAPI app at `app/api/server.py`.
Use that service for local development.

`main.py` is not the current startup path. It points to a missing legacy Streamlit app and should be treated as a leftover file, not the way to run the project.

## Repo layout

```text
.
├── app/                # Main FastAPI app, agents, workflows, repos, intelligence logic
├── bank_kb/            # Banking and payments knowledge base
├── agent/              # Agent prompts, playbooks, rubrics, and cards
├── docs/               # Architecture and API notes
├── IQ/frontend/        # Expo / React Native mobile client
├── IQ/backend/         # Older scaffolded backend workspace, not the main API used by the app
├── config.py           # Environment-driven runtime configuration
└── requirements.txt    # Python dependencies for the main backend
```

## Main stack

- Python + FastAPI
- PostgreSQL via SQLAlchemy
- LangChain / LangGraph-style agent tooling
- Groq or Ollama for LLM-backed flows
- Expo / React Native frontend

## Prerequisites

Before starting locally, make sure you have:

- Python 3.10+ installed
- Node.js 18+ installed
- npm installed
- PostgreSQL running and reachable from this project
- either:
  - a `GROQ_API_KEY`, or
  - a local Ollama instance if you want to use the Ollama fallback

## Environment setup

The backend reads from a root `.env` file through `config.py`.

Minimal variables to set:

```env
DATABASE_URL=postgresql://demo:demo@localhost:5433/payments_demo
CORS_ALLOW_ORIGINS=*

# Choose one LLM path
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=qwen/qwen3-32b

# Optional Ollama fallback
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
```

Notes:

- If `DATABASE_URL` is not set, the app defaults to `postgresql://demo:demo@localhost:5433/payments_demo`.
- The backend connects to Postgres during startup and builds a live schema registry immediately. If the database is down or the expected tables are missing, startup will fail.

## Backend setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the main API:

```bash
uvicorn app.api.server:app --reload --host 127.0.0.1 --port 8000
```

Useful backend URLs once it is running:

- Health check: `http://127.0.0.1:8000/health`
- Swagger UI: `http://127.0.0.1:8000/docs`

Quick verification:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Frontend setup

The mobile app lives in `IQ/frontend`.

Install frontend dependencies:

```bash
cd IQ/frontend
npm install
```

Start the Expo dev server:

```bash
npm run start
```

Useful frontend commands:

```bash
npm run ios
npm run android
npm run web
npm run lint
```

## Frontend API behavior

The frontend currently hardcodes the backend base URL in `IQ/frontend/src/services/api.ts`:

- iOS simulator and web use `http://localhost:8000/api/v1`
- Android emulator uses `http://10.0.2.2:8000/api/v1`

If you run the app on a physical device, you will likely need to change that base URL to your machine's LAN IP.

## Recommended local startup flow

Start the backend first:

```bash
source .venv/bin/activate
uvicorn app.api.server:app --reload --host 127.0.0.1 --port 8000
```

Then start the frontend in a second terminal:

```bash
cd IQ/frontend
npm install
npm run start
```

## Useful development commands

Backend:

```bash
source .venv/bin/activate
uvicorn app.api.server:app --reload --host 127.0.0.1 --port 8000
pytest
```

Frontend:

```bash
cd IQ/frontend
npm install
npm run start
npm run lint
```

## Important notes

- The primary backend entrypoint is `app/api/server.py`.
- `IQ/backend/server.py` exists, but it is not the main service the rest of this repo is structured around.
- `main.py` is a stale legacy entrypoint and should not be used to start the current system.
- `graphify-out/` is a local analysis artifact directory and is not part of the runtime.

## Additional docs

- Architecture overview: `docs/architecture.md`
- API notes: `docs/api_spec.md`


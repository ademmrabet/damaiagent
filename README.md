# DAM AI Agent

An AI assistant that answers questions about the African Development Bank's **Delegation of Authority Matrix (DAM)**: who is responsible, who approves, who checks, who must be informed, for any task in the matrix.

The matrix is a 79-page PDF with dense tables. Instead of searching it by hand, users ask in plain language (English, French, Spanish, Portuguese or Arabic) and get a grounded answer with the exact task, roles and footnotes behind it.

> Built as an end-of-studies project (PFE) at Polytech International for the African Development Bank.

## Demo

[![Demo video](assets/screenshots/chat.png)](VIDEO_LINK_HERE)

> Replace `VIDEO_LINK_HERE` with the demo video link (YouTube, Drive, or `assets/demo.mp4`).

## Screenshots

| Landing | Chat |
|---|---|
| ![Landing](assets/screenshots/landing.png) | ![Chat](assets/screenshots/chat.png) |

| Dashboard | Sharing (QR code) |
|---|---|
| ![Dashboard](assets/screenshots/dashboard.png) | ![Sharing](assets/screenshots/share.png) |

| Login | Voice and attachments |
|---|---|
| ![Login](assets/screenshots/login.png) | ![Voice and attachments](assets/screenshots/attachments.png) |

## Features

- **Grounded Q&A** on the matrix: lookup by task id (e.g. `3.112`) or by natural-language description, with follow-up questions that keep context.
- **Action codes and roles**: shows who is Responsible, Approves, Checks, Is consulted or informed, with authority levels and footnotes.
- **Glossary**: abbreviations of the matrix are expanded and can be asked about directly.
- **Typo tolerance** and small-talk handling.
- **Multilingual**: language auto-detection, answers translated back into the user's language, translated UI.
- **Hybrid LLM**: Groq (cloud) or Ollama (local) rephrase the answer; a grounding check rejects any rewrite that drops or changes facts and falls back to the deterministic answer.
- **Authentication**: email/password (bcrypt + JWT), Google and Microsoft sign-in, roles `administrator` and `analyst` (the first account is admin), rate-limited login.
- **Conversations** saved server-side, **sharing** by email or **QR code** (read-only), live updates through server-sent events.
- **Attachments**: upload a PDF, Word file or image and ask about it (S3-compatible storage).
- **Voice**: speech-to-text (Whisper via Groq) and read-aloud answers.
- **Dashboard** (admin only): KPIs and charts built from the graph, filterable by chapter.

## How it works

```
 DAM PDF ──► pdfplumber parsing ──► Pydantic nodes ──► nodes.json
                                                          │
                                                          ▼
                              NetworkX graph (327 DAM nodes + 132 roles,
                                     459 vertices, 2,108 edges)
                                                          │
 question ─► language/typo/tone ─► id lookup or TF-IDF search ─► rule-based agent
                                                          │
                                         structured, sourced answer
                                                          │
                              optional LLM rephrasing + grounding check
                                                          ▼
                                         FastAPI  ◄──►  React frontend
```

1. **Parsing** (`parsing/`, `extraction/`): reads the PDF geometry (rows, columns, action letters, footnotes, glossary) and rebuilds each task block.
2. **Modeling** (`schema/`, `modeling/`): validated Pydantic nodes (chapter, process, task, child task, variant) and a directed multigraph linking tasks to roles by action.
3. **Knowledge** (`knowledge/`): id resolution, TF-IDF + fuzzy text search, typo correction.
4. **Agent** (`agent/`): detects intent (approve, check, inform...), action-code questions, glossary and small talk, then builds the answer from the graph only.
5. **LLM layer** (`llm/`): provider routing (Groq / Ollama / none), translation, tone, attachment Q&A, transcription. The LLM only rephrases; facts always come from the graph.
6. **Web app** (`webapp/`): FastAPI backend, SQLAlchemy models, auth, sharing, SSE, storage; React + Vite frontend.

## Project structure

```
agent/        rule-based question answering
extraction/   PDF extraction helpers
knowledge/    search, id resolution, typo correction
llm/          Groq/Ollama providers, translation, tone, attachments, transcription
modeling/     node building and the knowledge graph
parsing/      row, column, hierarchy and glossary parsing
schema/       Pydantic data contract
scripts/      build_nodes_cache.py (parse the PDF once)
webapp/       FastAPI backend + frontend/ (React, Vite)
data/         raw PDF, reference tables, generated nodes.json
tests/        pytest suite
```

## Getting started

### With Docker

```bash
cp .env.example .env      # set at least JWT_SECRET_KEY
docker compose up --build
```

Open http://localhost:8000. Compose also starts a local Ollama container.

### Without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # set at least JWT_SECRET_KEY
python scripts/build_nodes_cache.py

cd webapp/frontend && npm install && npm run build && cd ../..
uvicorn webapp.backend:app --reload
```

Generate a secret with `python -c "import secrets; print(secrets.token_hex(32))"`.

### Configuration

| Variable | Purpose |
|---|---|
| `JWT_SECRET_KEY` | Signs login tokens (required) |
| `DATABASE_URL` | Postgres URL; SQLite file if unset |
| `GROQ_API_KEY`, `GROQ_MODEL` | Cloud LLM, translation, Whisper |
| `OLLAMA_HOST`, `OLLAMA_MODEL` | Local LLM |
| `AWS_*`, `NEON_BUCKET_NAME` | S3-compatible storage for attachments (optional) |
| `GOOGLE_*`, `MICROSOFT_*`, `BACKEND_BASE_URL` | OAuth sign-in (optional) |

Without an LLM key the app still works: answers come from the deterministic agent.

### Tests

```bash
pytest
```

## API overview

| Area | Endpoints |
|---|---|
| Ask | `POST /api/ask` |
| Auth | `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`, Google and Microsoft `login` / `callback` |
| Conversations | `GET/POST /api/conversations`, `GET/DELETE /api/conversations/{id}`, `POST .../messages` |
| Sharing | `POST/DELETE .../share`, `POST/DELETE .../share-link`, `POST /api/conversations/shared/{token}/claim` |
| Live updates | `GET /api/events` (SSE) |
| Files and voice | `POST /api/uploads`, `GET .../attachments/{key}`, `POST /api/transcribe` |
| Admin | `GET /api/dashboard/summary` |
| Misc | `GET /api/llm/config`, `GET /api/health` |

## Deployment

The Dockerfile builds the frontend, parses the PDF at build time (so the container does not run out of memory at startup) and serves everything with uvicorn on `$PORT`. The live version runs on Render with Neon Postgres and Neon object storage.

## Tech stack

Python, pdfplumber, Pydantic, NetworkX, scikit-learn, FastAPI, SQLAlchemy, passlib, python-jose, boto3 · React, Vite, GSAP, Chart.js · Groq, Ollama · Docker.

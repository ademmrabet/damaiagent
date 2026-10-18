# DAM AI Agent: video showcase

**Ask the DAM. Get the answer. With proof.**
An AI agent that turns the African Development Bank's Delegation of Authority Matrix (DAM) into instant, grounded answers: who initiates, approves, checks and must be informed for any task.

## Watch
- Full showcase (5 min): `final/DAM_Showcase_5min.mp4` (add link here once exported or uploaded)
- Pre-defense clips: `clips/demo1_core_agent.mp4` (0:50), `clips/demo2_platform.mp4` (0:50)

## Why it exists
A plain chatbot invents roles that sound right. This agent reads the matrix once, stores every task in a knowledge graph, and answers only from retrieved facts, with an honest refusal when the question is out of scope.

## Highlights
- Exact lookup by id, natural-language lookup, typo tolerance
- French, Spanish, Portuguese and Arabic questions and answers
- Mandatory Check/Verify and informed-party notes on every answer
- Grounding check with deterministic fallback
- Login, saved history, QR sharing, voice, document upload, KPI dashboard

## Stack
Python, pdfplumber, Pydantic, NetworkX, scikit-learn, FastAPI, React/Vite, Groq / Ollama, Postgres (Neon), Docker.

## Repo layout
- `SCRIPT_5MIN.md` narration timed to 5:00
- `SHOT_LIST.md` what to record, click by click
- `RECORDING_CHECKLIST.md` settings and export
- `raw/` your screen recordings (untouched)
- `clips/` short edits for the slides
- `final/` the 5-minute export

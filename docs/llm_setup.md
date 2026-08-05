# Setting up the hybrid LLM layer (local + API)

The agent works with zero setup - the "No LLM (template answer)" mode
in the chat UI is the default, and it's the same deterministic,
graph-backed answer the project has used since Day 7. Everything below
is only needed if you want to demo the "Ollama (local)", "Groq (API)",
or "Auto" modes to the professor.

## Why there's a fallback either way

Every LLM mode still runs the real lookup first (the knowledge graph
resolves the question and gathers the exact facts - roles, actions,
footnote numbers). The LLM's only job is to reword that into more
natural prose; if it's unreachable, times out, or its wording drops or
changes a fact, the app quietly falls back to the template answer
instead of showing an error or a wrong answer. So even a broken Ollama
install or a missing Groq key never breaks the demo - worst case, the
LLM toggle just behaves like "off" and shows a small "LLM unavailable"
note.

## Option A - Groq (cloud API, easiest to demo)

1. Create a free account at https://console.groq.com and generate an
   API key under **API Keys**.
2. In the project root, copy `.env.example` to `.env`:
   ```
   cp .env.example .env
   ```
3. Open `.env` and paste your key:
   ```
   GROQ_API_KEY=gsk_your_real_key_here
   ```
4. Start the server as usual (`python -m uvicorn webapp.backend:app --host 127.0.0.1 --port 8000`
   - first run the frontend build once, see the note below)
   and pick "Groq (API)" from the dropdown in the chat UI.

> **Frontend build, one-time (bare-metal only):** since the 2026-08-06
> React rewrite, the UI is built from `webapp/frontend/` rather than
> checked-in HTML files - run `cd webapp/frontend && npm install &&
> npm run build` once (and again after pulling any frontend change)
> before starting the server this way. Docker users don't need this -
> `docker compose up --build` does it automatically as part of the
> image build.

Groq's free tier is generous and the model (`llama-3.3-70b-versatile`
by default) responds in well under a second - good for a live demo.
Never commit `.env` or paste your key into chat/screenshots; `.env` is
already in `.gitignore`.

## Option B - Ollama (fully local, no internet needed at demo time)

1. Install Ollama from https://ollama.com/download (Windows installer).
2. Pull a model once, ahead of the meeting (this downloads a few GB,
   do it the night before, not five minutes prior):
   ```
   ollama pull llama3.1
   ```
3. Ollama runs its own background service after install - you don't
   need to start anything separately. Confirm it's up:
   ```
   ollama list
   ```
   should show `llama3.1` in the list.
4. Start the DAM server as usual and pick "Ollama (local)" from the
   dropdown. No API key, no network dependency once the model is
   pulled - good as a backup if the venue's wifi is unreliable.

If you want a different model, set `OLLAMA_MODEL` in `.env` to match
whatever you `ollama pull`.

## Option C - Auto (hybrid)

Picks Ollama if it's reachable at startup, otherwise falls back to
Groq if `GROQ_API_KEY` is set, otherwise behaves like "off". This is
the literal "hybrid local + API" the professor asked for - worth
demoing once by pointing out you could unplug the network and it
would keep answering, then plugging back in.

## Verifying it actually works before the meeting

Ask the same question with each mode and confirm the underlying facts
never change, only the phrasing does - that's the point being
demonstrated (retrieval is fixed and deterministic, the LLM only
touches wording). The "Show structured (template) answer" link under
any LLM-phrased reply lets you show both side by side live.

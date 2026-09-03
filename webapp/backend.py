
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from modeling.build_nodes import build_nodes
from modeling.nodes_cache import load_nodes
from modeling.graph import build_graph
from knowledge.search import build_search_index
from agent.qa import answer_question
from agent.generate import humanize_answer
from llm.router import resolve_provider
from llm.ollama_provider import OllamaProvider
from llm.groq_provider import GroqProvider
from llm.translate import detect_and_translate_to_english, translate_text, looks_non_english
from llm.tone import looks_emotional, detect_tone, apply_tone_prefix
from webapp.dashboard_data import build_summary

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = PROJECT_ROOT / "data" / "raw" / "updated dam file.pdf"
NODES_CACHE_PATH = PROJECT_ROOT / "data" / "processed" / "nodes.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="DAM AI Agent")

state = {}


@app.on_event("startup")
def load_dam():
    # Prefer the pre-built cache (baked into the Docker image at build
    # time via scripts/build_nodes_cache.py - see that file and
    # docs/decisions.md, 2026-08-06) - re-parsing the raw PDF with
    # pdfplumber on every process boot was heavy enough to OOM-kill the
    # container on Render's free tier. Falls back to a live parse when
    # no cache exists yet (fresh checkout, or data/raw/ changed and the
    # cache hasn't been regenerated), so this never hard-depends on the
    # cache being present.
    if NODES_CACHE_PATH.exists():
        nodes = load_nodes(NODES_CACHE_PATH)
    else:
        nodes = build_nodes(str(PDF_PATH))
    graph, _ = build_graph(nodes)
    vectorizer, matrix, searchable_ids = build_search_index(nodes)

    state["nodes"] = nodes
    state["graph"] = graph
    state["vectorizer"] = vectorizer
    state["matrix"] = matrix
    state["searchable_ids"] = searchable_ids


class Question(BaseModel):
    question: str
    llm: Optional[str] = None
    # The node_id this same chat thread last resolved to, if any - the
    # frontend tracks this per conversation (see Chat.jsx) and sends it
    # back so pronoun-style follow-ups ("who are the informed parties
    # for THAT ACTIVITY?") have a real anchor instead of resolve_query
    # guessing off incidental word overlap. See agent/qa.py's
    # answer_question docstring and docs/decisions.md, 2026-08-06.
    previous_node_id: Optional[str] = None
    # Explicit language picker override (2026-09-03, see docs/
    # decisions.md) for the ANSWER's language - independent of
    # whatever language the question text itself is in. None/"auto"/
    # omitted (the default) keeps the original auto-detect-from-the-
    # question behavior. Any other supported code (en/fr/es/pt/ar)
    # always wins - e.g. asking "who approves 3.111" in English while
    # the UI language picker is set to French still answers in French.
    target_language: Optional[str] = None


@app.post("/api/ask")
def ask(payload: Question):
    """
    Multi-language support (2026-08-06, extended 2026-09-03, see docs/
    decisions.md): the deterministic retrieval pipeline (id matching,
    TF-IDF search, intent detection, typo correction) is built
    entirely around the DAM's own English vocabulary - there's no
    realistic way to rebuild all of that per language. Instead, a
    non-English question is translated to English BEFORE it reaches
    answer_question() (so retrieval is completely unaffected, still
    the same tested logic), and the final answer is translated back
    afterward. looks_non_english() is a cheap, deterministic pre-
    filter so a plain English question (the overwhelming majority of
    traffic) never pays for the extra LLM round trips this requires.

    Two independent language concerns, deliberately decoupled: the
    language the QUESTION needs translating FROM (always detected from
    the question text itself, always translated TO English for
    retrieval) versus the language the ANSWER gets phrased IN (an
    explicit `target_language` picker selection always wins over
    whatever the question's own language was, falling back to the
    detected language only when no explicit selection was made). This
    is what lets someone type an English question with the UI language
    picker set to French and still get a French answer.
    """
    provider = resolve_provider(payload.llm) if payload.llm and payload.llm != "off" else None

    query_for_pipeline = payload.question
    detected_language = "en"
    translation_error = None

    if looks_non_english(payload.question):
        if provider is not None:
            translation = detect_and_translate_to_english(payload.question, provider)
            detected_language = translation["language"]
            translation_error = translation["error"]
            if translation["used_llm"] and detected_language != "en":
                query_for_pipeline = translation["translated_text"]
        else:
            # Can't detect/translate without an LLM - be honest about
            # why instead of silently matching non-English text
            # against an English-only search index and (most likely)
            # failing to resolve anything at all.
            translation_error = "Translation needs an LLM mode other than Off."

    if payload.target_language and payload.target_language != "auto":
        answer_language = payload.target_language
    else:
        answer_language = detected_language

    if answer_language != "en" and provider is None and not translation_error:
        # Only reachable here when the question itself looked English
        # (so the branch above never set translation_error) but the
        # user explicitly picked a non-English answer language with no
        # LLM available to produce one - be honest about that gap too,
        # same principle as the query-side check above.
        translation_error = "Translation needs an LLM mode other than Off."

    result = answer_question(
        query_for_pipeline,
        state["nodes"],
        state["graph"],
        state["vectorizer"],
        state["matrix"],
        state["searchable_ids"],
        previous_node_id=payload.previous_node_id,
    )
    deterministic_answer = result["answer"]

    if payload.llm and payload.llm != "off":
        if result.get("node_id") and result.get("roles"):
            # Real DAM facts to protect - the stricter, grounding-
            # checked path (agent/generate.py), phrased in
            # answer_language (explicit picker override if one was
            # given, else whatever the question was detected in).
            generation = humanize_answer(
                payload.question, result, provider, target_language=answer_language
            )
        elif answer_language != "en":
            # No facts to fabricate here (smalltalk/help/vague/out-of-
            # scope/invalid-id) - a static English message just needs
            # straight translation, no grounding check required.
            translated = translate_text(result["answer"], answer_language, provider)
            generation = {
                "text": translated["text"],
                "used_llm": translated["used_llm"],
                "provider": provider.name if translated["used_llm"] else None,
                "error": translated["error"],
            }
        else:
            generation = {"text": deterministic_answer, "used_llm": False, "provider": None, "error": None}

        result["answer"] = generation["text"]
        result["used_llm"] = generation["used_llm"]
        result["llm_provider"] = generation["provider"]
        result["llm_error"] = generation["error"]
    else:
        result["used_llm"] = False
        result["llm_provider"] = None
        result["llm_error"] = None

    result["deterministic_answer"] = deterministic_answer
    result["detected_language"] = detected_language
    result["answer_language"] = answer_language
    result["translation_error"] = translation_error

    # Tone detection (2026-09-03, see docs/decisions.md) - applies to
    # EVERY response type (Adem's explicit choice), not just grounded
    # DAM answers, which is exactly why this runs as a deterministic
    # prefix applied here at the very end rather than folded into
    # humanize_answer()'s prompt above: that path only runs for
    # grounded answers, but a frustrated "why won't this work AGAIN"
    # deserves the same warmer opening whether the answer underneath is
    # a fact lookup, a glossary lookup, or an honest out-of-scope
    # refusal. looks_emotional() gates the actual Groq call so ordinary
    # neutral questions (the large majority) never pay for it - same
    # pattern as looks_non_english() gating translation above. Detected
    # from payload.question (what the user actually typed), never the
    # translated/English version - tone is about how they expressed
    # themselves, not the retrieval-pipeline text.
    detected_tone = "neutral"
    if provider is not None and looks_emotional(payload.question):
        tone_result = detect_tone(payload.question, provider)
        detected_tone = tone_result["tone"]

    result["detected_tone"] = detected_tone
    result["answer"] = apply_tone_prefix(result["answer"], detected_tone, answer_language)

    return result


@app.get("/api/dashboard/summary")
def dashboard_summary():
    return build_summary(state["nodes"], state["graph"])


@app.get("/api/llm/config")
def llm_config():
    """
    The actual model names each mode would use right now - reads them
    from the same provider classes resolve_provider() itself uses, so
    this can never drift from reality the way a second, hand-written
    copy of "llama3.1" / "openai/gpt-oss-120b" in the frontend
    could. Respects env var overrides (OLLAMA_MODEL, GROQ_MODEL) same
    as the providers do - if Adem points OLLAMA_MODEL at a different
    pulled model, the UI reflects that without a code change.
    """
    return {
        "ollama_model": OllamaProvider().model,
        "groq_model": GroqProvider().model,
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "nodes_loaded": len(state.get("nodes", {}))}


@app.get("/")
def landing():
    return FileResponse(STATIC_DIR / "landing.html")


@app.get("/chat")
def chat_page():
    return FileResponse(STATIC_DIR / "chat.html")


@app.get("/dashboard")
def dashboard_page():
    return FileResponse(STATIC_DIR / "dashboard.html")


# The React build (webapp/frontend/, built via `npm run build`) emits
# its bundled JS/CSS under webapp/static/assets - Vite's default asset
# base path is "/", so this has to be mounted at "/assets" to match
# what the built HTML actually references. "/static" is kept too for
# anything that ever needs the raw directory (e.g. favicon), same
# mount point as before this rewrite.
#
# check_dir=False on both: webapp/static (and its assets/ subfolder)
# is now a BUILD ARTIFACT, not something committed to git (see
# .gitignore) - it only exists after `npm run build` has run. Without
# this, importing this module before that build step (e.g. a test
# suite run on a fresh checkout) would crash at import time with
# "directory does not exist" instead of failing only the requests
# that actually need the built files.
app.mount(
    "/assets",
    StaticFiles(directory=str(STATIC_DIR / "assets"), check_dir=False),
    name="assets",
)
app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR), check_dir=False),
    name="static",
)

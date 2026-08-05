
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from modeling.build_nodes import build_nodes
from modeling.graph import build_graph
from knowledge.search import build_search_index
from agent.qa import answer_question
from agent.generate import humanize_answer
from llm.router import resolve_provider
from llm.ollama_provider import OllamaProvider
from llm.groq_provider import GroqProvider
from webapp.dashboard_data import build_summary

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = PROJECT_ROOT / "data" / "raw" / "updated dam file.pdf"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="DAM AI Agent")

state = {}


@app.on_event("startup")
def load_dam():
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


@app.post("/api/ask")
def ask(payload: Question):
    result = answer_question(
        payload.question,
        state["nodes"],
        state["graph"],
        state["vectorizer"],
        state["matrix"],
        state["searchable_ids"],
    )
    deterministic_answer = result["answer"]

    if payload.llm and payload.llm != "off":
        provider = resolve_provider(payload.llm)
        generation = humanize_answer(payload.question, result, provider)
        result["answer"] = generation["text"]
        result["used_llm"] = generation["used_llm"]
        result["llm_provider"] = generation["provider"]
        result["llm_error"] = generation["error"]
    else:
        result["used_llm"] = False
        result["llm_provider"] = None
        result["llm_error"] = None

    result["deterministic_answer"] = deterministic_answer
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
    copy of "llama3.1" / "llama-3.3-70b-versatile" in the frontend
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

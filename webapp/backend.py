
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from jose import JWTError
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

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
from llm.transcribe import transcribe_audio
from llm.base import LLMUnavailableError
from llm.attachments import UnsupportedAttachmentError, answer_about_attachment
from webapp.conversations import (
    append_message,
    claim_share_link,
    conversation_has_attachment,
    create_conversation,
    delete_conversation,
    get_conversation_for_viewing,
    get_or_create_share_link,
    get_owned_conversation,
    list_own_conversations,
    list_shared_with_me,
    revoke_share_link,
    serialize_conversation,
    serialize_share_link,
    share_conversation,
    unshare_conversation,
)
from webapp.dashboard_data import build_summary
from webapp.events import notify_user, notify_users, subscribe, unsubscribe
from webapp.qr import qr_svg_data_uri
from webapp.storage import download_attachment, presign_download, upload_attachment
from webapp.db import get_db, init_db
from webapp.models import Role, User
from webapp.auth import (
    JWT_SECRET_KEY,
    check_login_rate_limit,
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from webapp.oauth import GOOGLE_CONFIGURED, MICROSOFT_CONFIGURED, get_or_create_oauth_user, oauth

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = PROJECT_ROOT / "data" / "raw" / "updated dam file.pdf"
NODES_CACHE_PATH = PROJECT_ROOT / "data" / "processed" / "nodes.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="DAM AI Agent")

app.add_middleware(SessionMiddleware, secret_key=JWT_SECRET_KEY)

logger = logging.getLogger("webapp.backend")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    2026-09-20 (see docs/decisions.md): without this, any bug that
    escapes as a bare Exception (not an HTTPException) falls through to
    Starlette's own default handler, which returns the literal plain-
    text body "Internal Server Error" - not JSON. Every api.js function
    calls `res.json()` on the response, so that plain-text body used to
    surface to the user as a cryptic `Unexpected token 'I', "Internal
    S"... is not valid JSON` instead of any usable message (this is
    exactly what happened on a PDF upload attempt that hit some
    still-unidentified server-side fault - see the still-open item in
    docs/decisions.md). This handler doesn't fix whatever the
    underlying bug is - it logs the real traceback server-side via
    logger.exception (so it's still visible in Render's logs) and
    returns a generic, non-leaking JSON body so the frontend can at
    least show *something* coherent and so future crashes are
    immediately diagnosable from the client-visible error instead of
    only from a log line nobody was watching at the time.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Something went wrong on the server. Please try again."},
    )

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")

state = {}


@app.on_event("startup")
def load_dam():
    if NODES_CACHE_PATH.exists():
        nodes = load_nodes(NODES_CACHE_PATH)
    else:
        nodes = build_nodes(str(PDF_PATH))
    graph, _ = build_graph(nodes)
    vectorizer, matrix, searchable_ids = build_search_index(nodes)

    init_db()

    state["nodes"] = nodes
    state["graph"] = graph
    state["vectorizer"] = vectorizer
    state["matrix"] = matrix
    state["searchable_ids"] = searchable_ids


class AttachmentRef(BaseModel):
    key: str
    content_type: str
    filename: str


class Question(BaseModel):
    question: str
    llm: Optional[str] = None
    previous_node_id: Optional[str] = None
    target_language: Optional[str] = None
    attachment: Optional[AttachmentRef] = None


def _attachment_answer(
    answer_text: str, used_llm: bool, provider_name: Optional[str], answer_language: str
) -> dict:
    """
    Every key a normal /api/ask response carries, so Chat.jsx's meta
    construction (which reads node_id/method/score/etc. unconditionally)
    doesn't need a second code path for this - it just gets None/neutral
    values for the fields that only make sense for a DAM lookup, plus
    `source: "attachment"` so the frontend can render this distinctly
    per FR13's own requirement that an attachment-grounded answer be
    "clearly distinguished from answers grounded in the DAM."
    """
    return {
        "answer": answer_text,
        "source": "attachment",
        "node_id": None,
        "method": "attachment",
        "score": None,
        "roles": None,
        "used_llm": used_llm,
        "llm_provider": provider_name,
        "llm_error": None,
        "deterministic_answer": None,
        "detected_language": "en",
        "answer_language": answer_language,
        "translation_error": None,
        "detected_tone": "neutral",
    }


def _authenticated_user_for_attachment(request: Request, db: Session) -> User:
    """
    /api/ask is otherwise unauthenticated (plain DAM lookups are
    intentionally open), but reading an attachment's actual content
    is not - this is called only on the attachment branch below, so a
    normal question never needs a token while asking about a file
    always does.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(auth_header[len("Bearer ") :])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return user


def _ask_about_attachment(payload: Question, request: Request, db: Session) -> dict:
    user = _authenticated_user_for_attachment(request, db)

    # Keys are always minted as attachments/{uploader_id}/{uuid}-{filename}
    # (see webapp/storage.py's upload_attachment) - this is what stops
    # a caller from passing someone else's key and having the server
    # read it back to them.
    if not payload.attachment.key.startswith(f"attachments/{user.id}/"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't read this attachment")

    # "Switch to Auto automatically" (2026-09-20, see docs/decisions.md)
    # - an attached file always needs a model to read it, so a picker
    # left on Off (or an Auto that resolved to nothing) falls back to
    # Auto rather than refusing outright. An explicit Groq/Ollama
    # choice is respected as-is, even if that provider then turns out
    # not to support the attachment (see answer_about_attachment's
    # image-without-vision case) - that's a clearer failure than
    # silently overriding a deliberate choice.
    provider = resolve_provider(payload.llm) if payload.llm and payload.llm != "off" else None
    if provider is None:
        provider = resolve_provider("auto")
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No language model is available right now, so this attachment can't be read.",
        )

    contents = download_attachment(payload.attachment.key)
    answer_language = payload.target_language if payload.target_language and payload.target_language != "auto" else "en"

    try:
        result = answer_about_attachment(
            payload.question,
            payload.attachment.content_type,
            payload.attachment.filename,
            contents,
            provider,
            target_language=payload.target_language,
        )
    except UnsupportedAttachmentError as exc:
        return _attachment_answer(str(exc), used_llm=False, provider_name=None, answer_language=answer_language)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return _attachment_answer(result["text"], used_llm=True, provider_name=result["provider"], answer_language=answer_language)


@app.post("/api/ask")
def ask(payload: Question, request: Request, db: Session = Depends(get_db)):
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
    if payload.attachment is not None:
        return _ask_about_attachment(payload, request, db)

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
            translation_error = "Translation needs an LLM mode other than Off."

    if payload.target_language and payload.target_language != "auto":
        answer_language = payload.target_language
    else:
        answer_language = detected_language

    if answer_language != "en" and provider is None and not translation_error:
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
            generation = humanize_answer(
                payload.question, result, provider, target_language=answer_language
            )
        elif answer_language != "en":
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

    detected_tone = "neutral"
    if provider is not None and looks_emotional(payload.question):
        tone_result = detect_tone(payload.question, provider)
        detected_tone = tone_result["tone"]

    result["detected_tone"] = detected_tone
    result["answer"] = apply_tone_prefix(result["answer"], detected_tone, answer_language)

    return result


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    name: Optional[str] = None
    role: str


def _auth_response(user: User) -> AuthResponse:
    role = user.role.value if hasattr(user.role, "value") else user.role
    return AuthResponse(access_token=create_access_token(user), email=user.email, name=user.name, role=role)


@app.post("/api/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """
    Email/password signup. The first account ever created on a fresh
    database becomes an administrator (so there's a way in without
    manual database surgery); every account after that defaults to
    analyst. This is a deliberate bootstrap convenience, not a
    long-term admin-management story - promoting a second admin
    still needs a direct database edit for now.
    """
    if len(payload.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    is_first_user = db.query(User).count() == 0

    user = User(
        email=payload.email.lower(),
        name=payload.name,
        hashed_password=hash_password(payload.password),
        role=Role.administrator if is_first_user else Role.analyst,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    db.refresh(user)

    return _auth_response(user)


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    check_login_rate_limit(request.client.host if request.client else "unknown")

    user = db.query(User).filter(User.email == payload.email.lower()).first()

    generic_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    if user is None or user.hashed_password is None:
        raise generic_error

    if not verify_password(payload.password, user.hashed_password):
        raise generic_error

    return _auth_response(user)


@app.get("/api/auth/me")
def auth_me(user: User = Depends(get_current_user)):
    role = user.role.value if hasattr(user.role, "value") else user.role
    return {"email": user.email, "name": user.name, "role": role}


class NewMessage(BaseModel):
    role: str
    text: str
    meta: Optional[dict] = None


class ShareRequest(BaseModel):
    email: EmailStr


@app.get("/api/conversations")
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "own": [serialize_conversation(c, is_owner=True) for c in list_own_conversations(db, user)],
        "shared_with_me": [
            serialize_conversation(c, is_owner=False) for c in list_shared_with_me(db, user)
        ],
    }


@app.post("/api/conversations")
def new_conversation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = create_conversation(db, user)
    return serialize_conversation(conversation, is_owner=True)


@app.get("/api/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    conversation = get_conversation_for_viewing(db, conversation_id, user)
    return serialize_conversation(conversation, is_owner=conversation.owner_id == user.id)


@app.post("/api/conversations/{conversation_id}/messages")
def add_message(
    conversation_id: str,
    payload: NewMessage,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = get_owned_conversation(db, conversation_id, user)
    updated = append_message(db, conversation, payload.dict())
    # Only the owner can post (see models.py's ConversationShare
    # docstring), but anyone the conversation is shared with should
    # see the new message without refreshing - see webapp/events.py.
    notify_users(
        [share.shared_with_user_id for share in updated.shares],
        {"type": "message", "conversation_id": conversation_id},
    )
    return serialize_conversation(updated, is_owner=True)


@app.delete("/api/conversations/{conversation_id}")
def remove_conversation(
    conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    conversation = get_owned_conversation(db, conversation_id, user)
    delete_conversation(db, conversation)
    return {"deleted": True}


@app.post("/api/conversations/{conversation_id}/share")
def share(
    conversation_id: str,
    payload: ShareRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = get_owned_conversation(db, conversation_id, user)
    new_share = share_conversation(db, conversation, user, payload.email)
    notify_user(new_share.shared_with_user_id, {"type": "shared", "conversation_id": conversation_id})
    return serialize_conversation(conversation, is_owner=True)


@app.delete("/api/conversations/{conversation_id}/share/{target_user_id}")
def unshare(
    conversation_id: str,
    target_user_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = get_owned_conversation(db, conversation_id, user)
    unshare_conversation(db, conversation, target_user_id)
    notify_user(target_user_id, {"type": "unshared", "conversation_id": conversation_id})
    return serialize_conversation(conversation, is_owner=True)


class ShareLinkResponse(BaseModel):
    token: str
    url: str
    qr_svg_data_uri: str
    expires_at: Optional[str]


@app.post("/api/conversations/{conversation_id}/share-link", response_model=ShareLinkResponse)
def create_share_link(
    conversation_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    "Share via QR code" - reuses an existing, still-valid link if one
    was already generated (see get_or_create_share_link), so reopening
    this panel doesn't invalidate a code someone already scanned.
    request.base_url (rather than a separately configured env var)
    builds the link, since the frontend is served from this same
    FastAPI app at the same origin in every environment this actually
    runs in (see vite.config.js's multi-page build comment).
    """
    conversation = get_owned_conversation(db, conversation_id, user)
    link = get_or_create_share_link(db, conversation, user)
    url = f"{str(request.base_url).rstrip('/')}/chat?share_token={link.token}"
    return serialize_share_link(link, url, qr_svg_data_uri(url))


@app.delete("/api/conversations/{conversation_id}/share-link")
def delete_share_link(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = get_owned_conversation(db, conversation_id, user)
    revoke_share_link(db, conversation)
    return {"revoked": True}


@app.post("/api/conversations/shared/{token}/claim")
def claim_share(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = claim_share_link(db, token, user)
    if conversation.owner_id != user.id:
        notify_user(conversation.owner_id, {"type": "shared", "conversation_id": conversation.id})
    return serialize_conversation(conversation, is_owner=conversation.owner_id == user.id)


@app.get("/api/events")
async def events(token: str, db: Session = Depends(get_db)):
    """
    Server-Sent Events stream backing the sidebar's real-time refresh
    (see webapp/events.py and useConversations.js). EventSource can't
    set an Authorization header, so the token travels as a query
    param instead - same JWT, same 8-hour expiry, just carried
    differently for this one connection. A heartbeat comment every 25
    seconds keeps the connection from being treated as idle and
    dropped by an intermediate proxy; the frontend's own 30-second
    poll is the backstop if the stream drops anyway.
    """
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")

    user_id = str(user.id)

    async def stream():
        queue = subscribe(user_id)
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            unsubscribe(user_id, queue)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/uploads")
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """
    Any logged-in user can upload - the upload itself isn't tied to a
    conversation yet (the message that ends up referencing it, via
    `meta.attachment` on the POST to /messages, hasn't been created at
    this point). Access control happens on the READ side instead - see
    get_attachment_url below - which is what actually decides who can
    fetch this file back.
    """
    contents = await file.read()
    return upload_attachment(file, str(user.id), contents)


@app.get("/api/conversations/{conversation_id}/attachments/{key:path}")
def get_attachment_url(
    conversation_id: str,
    key: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deliberately doesn't hand back a permanent link - see
    webapp/storage.py's presign_download docstring for why a fresh,
    short-lived URL is generated on every read instead. Reuses the
    exact same owner-or-shared-with check every other read of this
    conversation goes through, then additionally checks the key is
    really something that was attached to a message in THIS
    conversation - otherwise a valid, logged-in user could try
    guessing at other people's attachment keys via a conversation they
    happen to own.
    """
    conversation = get_conversation_for_viewing(db, conversation_id, user)
    if not conversation_has_attachment(conversation, key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found in this conversation")
    return {"url": presign_download(key)}


MAX_VOICE_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB - a spoken question, not a podcast


@app.post("/api/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """
    Backs the composer's mic button - reuses the same Groq account the
    chat's "Groq"/"Auto" LLM modes already use (see llm/transcribe.py),
    so voice input needs no new API key or provider setup, only
    GROQ_API_KEY already being set. Returns plain transcribed text for
    the frontend to drop into the input box - it's still sent as a
    normal typed question from there, so nothing downstream (grounding,
    intent detection, language handling) needs to know voice was ever
    involved.
    """
    contents = await file.read()
    if len(contents) > MAX_VOICE_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Recording is too long - the limit is {MAX_VOICE_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        text = transcribe_audio(contents, filename=file.filename or "audio.webm")
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return {"text": text}


@app.get("/api/auth/google/login")
async def google_login(request: Request):
    if not GOOGLE_CONFIGURED:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured yet")
    redirect_uri = f"{BACKEND_BASE_URL}/api/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/api/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    if not GOOGLE_CONFIGURED:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured yet")

    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or await oauth.google.userinfo(token=token)

    user = get_or_create_oauth_user(
        db, provider="google", subject=userinfo["sub"], email=userinfo["email"], name=userinfo.get("name")
    )
    jwt_token = create_access_token(user)
    return RedirectResponse(f"/login?token={jwt_token}")


@app.get("/api/auth/microsoft/login")
async def microsoft_login(request: Request):
    if not MICROSOFT_CONFIGURED:
        raise HTTPException(status_code=503, detail="Microsoft sign-in is not configured yet")
    redirect_uri = f"{BACKEND_BASE_URL}/api/auth/microsoft/callback"
    return await oauth.microsoft.authorize_redirect(request, redirect_uri)


@app.get("/api/auth/microsoft/callback")
async def microsoft_callback(request: Request, db: Session = Depends(get_db)):
    if not MICROSOFT_CONFIGURED:
        raise HTTPException(status_code=503, detail="Microsoft sign-in is not configured yet")

    token = await oauth.microsoft.authorize_access_token(request)
    userinfo = token.get("userinfo") or await oauth.microsoft.userinfo(token=token)

    user = get_or_create_oauth_user(
        db, provider="microsoft", subject=userinfo["sub"], email=userinfo["email"], name=userinfo.get("name")
    )
    jwt_token = create_access_token(user)
    return RedirectResponse(f"/login?token={jwt_token}")


@app.get("/api/dashboard/summary")
def dashboard_summary(user: User = Depends(require_admin)):
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


@app.get("/login")
def login_page():
    return FileResponse(STATIC_DIR / "login.html")


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

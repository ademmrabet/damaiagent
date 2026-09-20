"""
Speech-to-text for the chat composer's mic button (2026-09-20, see
docs/decisions.md) - a standalone function rather than another
LLMProvider, since transcription (audio in, text out) isn't a chat
completion and doesn't fit that interface. Reuses GROQ_API_KEY, same
as llm/groq_provider.py, rather than asking Adem to manage a second
API key for what's already the same account.
"""

import os

import requests

from llm.base import LLMUnavailableError

DEFAULT_MODEL = "whisper-large-v3-turbo"
API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm", timeout: int = 30) -> str:
    """
    Sends a recorded clip to Groq's (OpenAI-compatible) Whisper
    endpoint and returns the transcript as plain text. Raises
    LLMUnavailableError on anything wrong - missing key, network
    failure, timeout, unexpected response shape - mirroring
    GroqProvider.chat()'s error contract so callers (webapp/backend.py)
    only need to handle one exception type.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise LLMUnavailableError(
            "GROQ_API_KEY is not set - voice input needs the same key the Groq chat mode uses."
        )

    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, audio_bytes)},
            data={"model": DEFAULT_MODEL},
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise LLMUnavailableError(f"Groq transcription request failed: {exc}") from exc

    body = resp.json()
    try:
        return body["text"]
    except (KeyError, TypeError) as exc:
        raise LLMUnavailableError(f"Unexpected Groq transcription response shape: {body!r}") from exc

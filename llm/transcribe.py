import os

import requests

from llm.base import LLMUnavailableError

DEFAULT_MODEL = "whisper-large-v3-turbo"
API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


# send a voice clip to groq whisper and return the text
def transcribe_audio(
    audio_bytes: bytes, filename: str = "audio.webm", timeout: int = 30
) -> str:
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
        raise LLMUnavailableError(
            f"Unexpected Groq transcription response shape: {body!r}"
        ) from exc

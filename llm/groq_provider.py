import os

import requests

from llm.base import LLMProvider, LLMUnavailableError

DEFAULT_MODEL = "openai/gpt-oss-120b"
API_URL = "https://api.groq.com/openai/v1/chat/completions"

# The one multimodal model Groq currently serves (see
# https://console.groq.com/docs/vision, checked 2026-09-20) - fixed
# rather than exposed via GROQ_MODEL/an env var like the text model is,
# since a vision request needs a vision-capable model specifically and
# there is currently exactly one to pick from. If Groq adds another,
# this is the one line that needs to change.
VISION_MODEL = "qwen/qwen3.8-27b"


class GroqProvider(LLMProvider):
    name = "groq"

    # Distinguishes Groq from OllamaProvider for callers deciding
    # whether an image attachment can be answered at all (see
    # llm/attachments.py) - Ollama's vision support depends entirely on
    # which model happens to be pulled locally, which this app has no
    # way to know, so it's treated as not vision-capable rather than
    # guessed at.
    supports_vision = True

    def __init__(self, api_key=None, model=None, timeout=30):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model or os.environ.get("GROQ_MODEL") or DEFAULT_MODEL
        self.timeout = timeout

    def chat(self, system, user, temperature=0.2, max_tokens=512):
        if not self.api_key:
            raise LLMUnavailableError(
                "GROQ_API_KEY is not set - export it or put it in a .env file "
                "before selecting the Groq provider."
            )

        try:
            resp = requests.post(
                API_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "max_completion_tokens": max_tokens,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise LLMUnavailableError(f"Groq request failed (model={self.model}): {exc}") from exc

        body = resp.json()
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError(f"Unexpected Groq response shape: {body!r}") from exc

    def chat_with_image(self, system, user_text, image_data_url, temperature=0.2, max_tokens=1024):
        """
        Same shape as chat(), except the user message is a content list
        (text part + image part) per Groq's vision format, and it's
        always sent to VISION_MODEL rather than self.model - the
        configured text model (e.g. openai/gpt-oss-120b) has no vision
        capability at all, so there's no meaningful per-instance
        override here the way there is for chat()'s model.
        """
        if not self.api_key:
            raise LLMUnavailableError(
                "GROQ_API_KEY is not set - export it or put it in a .env file "
                "before selecting the Groq provider."
            )

        try:
            resp = requests.post(
                API_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": VISION_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_text},
                                {"type": "image_url", "image_url": {"url": image_data_url}},
                            ],
                        },
                    ],
                    "temperature": temperature,
                    "max_completion_tokens": max_tokens,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise LLMUnavailableError(f"Groq vision request failed (model={VISION_MODEL}): {exc}") from exc

        body = resp.json()
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError(f"Unexpected Groq response shape: {body!r}") from exc

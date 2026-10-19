import os

import requests

from llm.base import LLMProvider, LLMUnavailableError

DEFAULT_MODEL = "openai/gpt-oss-120b"
API_URL = "https://api.groq.com/openai/v1/chat/completions"

VISION_MODEL = "qwen/qwen3.8-27b"


# cloud llm through the groq api
class GroqProvider(LLMProvider):
    name = "groq"

    supports_vision = True

    def __init__(self, api_key=None, model=None, timeout=30):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model or os.environ.get("GROQ_MODEL") or DEFAULT_MODEL
        self.timeout = timeout

    # send a text prompt to groq and return the reply
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
            raise LLMUnavailableError(
                f"Groq request failed (model={self.model}): {exc}"
            ) from exc

        body = resp.json()
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError(
                f"Unexpected Groq response shape: {body!r}"
            ) from exc

    # same as chat but with an image for the vision model
    def chat_with_image(
        self, system, user_text, image_data_url, temperature=0.2, max_tokens=1024
    ):
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
                                {
                                    "type": "image_url",
                                    "image_url": {"url": image_data_url},
                                },
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
            raise LLMUnavailableError(
                f"Groq vision request failed (model={VISION_MODEL}): {exc}"
            ) from exc

        body = resp.json()
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError(
                f"Unexpected Groq response shape: {body!r}"
            ) from exc

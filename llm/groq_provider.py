import os

import requests

from llm.base import LLMProvider, LLMUnavailableError

# llama-3.3-70b-versatile was the original default but Groq shut it
# down for standard/developer API keys on 2026-08-16 (moved to
# Enterprise-only, contact-sales pricing - see console.groq.com/docs/
# models, confirmed live against a real 404 from production, not
# assumed - see docs/decisions.md). openai/gpt-oss-120b is Groq's
# current flagship production model on the standard plan: similar
# speed (~500 t/s), 131K context, and - unlike the smaller 20B variant
# - strong enough instruction-following for this app's strict grounded-
# phrasing and two-line translation-format prompts.
DEFAULT_MODEL = "openai/gpt-oss-120b"
API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(LLMProvider):
    name = "groq"

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

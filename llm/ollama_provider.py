import os

import requests

from llm.base import LLMProvider, LLMUnavailableError

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1"


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, host=None, model=None, timeout=30):
        self.host = (host or os.environ.get("OLLAMA_HOST") or DEFAULT_HOST).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL") or DEFAULT_MODEL
        self.timeout = timeout

    def is_available(self):
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=2)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def chat(self, system, user, temperature=0.2, max_tokens=512):
        try:
            resp = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise LLMUnavailableError(
                f"Ollama request failed (host={self.host}, model={self.model}): {exc}"
            ) from exc

        body = resp.json()
        try:
            return body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMUnavailableError(f"Unexpected Ollama response shape: {body!r}") from exc

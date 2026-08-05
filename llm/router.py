import os

from llm.base import LLMUnavailableError
from llm.groq_provider import GroqProvider
from llm.ollama_provider import OllamaProvider

VALID_MODES = {"off", "ollama", "groq", "auto"}


def resolve_provider(mode):
    """
    Turn a requested mode into a concrete provider instance, or None
    for "off" (deterministic answer only - no LLM involved).

    "auto" is the hybrid behavior: prefer the cloud API (Groq - fast,
    a stronger model, no local install needed) and only fall back to
    the local model if a Groq key genuinely isn't configured. This is
    a startup-time choice, not per-token routing - good enough for a
    Q&A agent where nothing depends on mid-response failover.

    (Reversed 2026-08-06 from the original "prefer local" order at
    Adem's request - see docs/decisions.md. Ollama being unreachable
    is no longer even checked when a Groq key is present: is_available()
    was only ever needed to detect a genuinely-down local server, and
    with Groq preferred first that check now only matters on the
    fallback path below.)
    """
    if mode is None or mode == "off":
        return None
    if mode == "ollama":
        return OllamaProvider()
    if mode == "groq":
        return GroqProvider()
    if mode == "auto":
        if os.environ.get("GROQ_API_KEY"):
            return GroqProvider()
        ollama = OllamaProvider()
        if ollama.is_available():
            return ollama
        return None
    raise ValueError(f"Unknown LLM mode {mode!r} - expected one of {sorted(VALID_MODES)}")

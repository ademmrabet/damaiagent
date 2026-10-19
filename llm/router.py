import os

from llm.base import LLMUnavailableError
from llm.groq_provider import GroqProvider
from llm.ollama_provider import OllamaProvider

VALID_MODES = {"off", "ollama", "groq", "auto"}


# pick groq, ollama or none depending on the mode
def resolve_provider(mode):
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
    raise ValueError(
        f"Unknown LLM mode {mode!r} - expected one of {sorted(VALID_MODES)}"
    )

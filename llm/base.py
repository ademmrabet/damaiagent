from abc import ABC, abstractmethod


class LLMUnavailableError(Exception):
    """
    Raised for any reason a provider couldn't produce a completion -
    missing config, network failure, timeout, non-2xx response. Kept
    as one exception type so callers (agent/generate.py) can catch a
    single thing and fall back, instead of having to know every
    provider's own exception hierarchy.
    """


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def chat(self, system, user, temperature=0.2, max_tokens=512):
        """
        Send one system + one user message, return the assistant's
        reply as plain text. Raises LLMUnavailableError on failure.
        """

    def is_available(self):
        """
        Cheap, fast reachability check (not a full completion) used by
        the "auto" hybrid mode to decide which provider to try first
        without paying a full generation timeout. Default: assume
        available: providers whose availability check is actually
        cheap (Ollama) override this; Groq's own chat() failing is
        already fast enough that a separate check isn't needed.
        """
        return True

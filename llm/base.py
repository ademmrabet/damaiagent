from abc import ABC, abstractmethod


# raised when no llm answer could be produced
class LLMUnavailableError(Exception):
    pass


# common interface every llm engine implements
class LLMProvider(ABC):
    name: str

    supports_vision = False

    # raises LLMUnavailableError on failure
    @abstractmethod
    def chat(self, system, user, temperature=0.2, max_tokens=512):
        pass

    # assume available
    def is_available(self):
        return True

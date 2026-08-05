from unittest.mock import Mock, patch

import pytest
import requests

from llm.base import LLMUnavailableError
from llm.groq_provider import GroqProvider
from llm.ollama_provider import OllamaProvider
from llm.router import resolve_provider


def _ok_response(json_body):
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json = Mock(return_value=json_body)
    resp.status_code = 200
    return resp


class TestOllamaProvider:
    def test_chat_success(self):
        provider = OllamaProvider(host="http://fake-ollama:11434", model="llama3.1")
        with patch("llm.ollama_provider.requests.post") as post:
            post.return_value = _ok_response({"message": {"content": "hello there"}})
            result = provider.chat("system", "user")
        assert result == "hello there"
        assert post.call_args.kwargs["json"]["model"] == "llama3.1"

    def test_chat_network_failure_raises_unavailable(self):
        provider = OllamaProvider(host="http://fake-ollama:11434")
        with patch("llm.ollama_provider.requests.post", side_effect=requests.ConnectionError("refused")):
            with pytest.raises(LLMUnavailableError):
                provider.chat("system", "user")

    def test_chat_unexpected_shape_raises_unavailable(self):
        provider = OllamaProvider(host="http://fake-ollama:11434")
        with patch("llm.ollama_provider.requests.post") as post:
            post.return_value = _ok_response({"unexpected": "shape"})
            with pytest.raises(LLMUnavailableError):
                provider.chat("system", "user")

    def test_is_available_true(self):
        provider = OllamaProvider(host="http://fake-ollama:11434")
        with patch("llm.ollama_provider.requests.get") as get:
            get.return_value = Mock(status_code=200)
            assert provider.is_available() is True

    def test_is_available_false_on_connection_error(self):
        provider = OllamaProvider(host="http://fake-ollama:11434")
        with patch("llm.ollama_provider.requests.get", side_effect=requests.ConnectionError()):
            assert provider.is_available() is False


class TestGroqProvider:
    def test_chat_without_api_key_raises_unavailable_no_network_call(self, monkeypatch):
        # Explicitly cleared rather than relying on it being absent -
        # this test previously passed in isolation but failed whenever
        # run in the same session as test_backend.py, because
        # importing webapp.backend triggers load_dotenv(), which picks
        # up a real local GROQ_API_KEY from .env and leaks it in here.
        # Documented as a known gap in docs/decisions.md (2026-08-06);
        # fixing it directly now since it kept resurfacing.
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        provider = GroqProvider(api_key=None)
        with patch("llm.groq_provider.requests.post") as post:
            with pytest.raises(LLMUnavailableError):
                provider.chat("system", "user")
        post.assert_not_called()

    def test_chat_success(self):
        provider = GroqProvider(api_key="fake-key", model="llama-3.3-70b-versatile")
        with patch("llm.groq_provider.requests.post") as post:
            post.return_value = _ok_response(
                {"choices": [{"message": {"content": "grounded reply"}}]}
            )
            result = provider.chat("system", "user")
        assert result == "grounded reply"
        headers = post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer fake-key"

    def test_chat_network_failure_raises_unavailable(self):
        provider = GroqProvider(api_key="fake-key")
        with patch("llm.groq_provider.requests.post", side_effect=requests.Timeout()):
            with pytest.raises(LLMUnavailableError):
                provider.chat("system", "user")


class TestRouter:
    def test_off_returns_none(self):
        assert resolve_provider("off") is None
        assert resolve_provider(None) is None

    def test_explicit_ollama(self):
        assert isinstance(resolve_provider("ollama"), OllamaProvider)

    def test_explicit_groq(self):
        assert isinstance(resolve_provider("groq"), GroqProvider)

    def test_auto_prefers_groq_when_key_is_set(self, monkeypatch):
        # Reversed 2026-08-06 at Adem's request: Auto now prefers the
        # API first. Ollama being reachable shouldn't matter at all
        # here - is_available() is never even called on this path.
        monkeypatch.setenv("GROQ_API_KEY", "fake-key")
        with patch("llm.router.OllamaProvider.is_available", return_value=True) as is_available:
            provider = resolve_provider("auto")
        assert isinstance(provider, GroqProvider)
        is_available.assert_not_called()

    def test_auto_falls_back_to_ollama_when_no_groq_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with patch("llm.router.OllamaProvider.is_available", return_value=True):
            provider = resolve_provider("auto")
        assert isinstance(provider, OllamaProvider)

    def test_auto_returns_none_when_nothing_available(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with patch("llm.router.OllamaProvider.is_available", return_value=False):
            provider = resolve_provider("auto")
        assert provider is None

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            resolve_provider("not-a-real-mode")

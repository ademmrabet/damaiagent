from unittest.mock import Mock, patch

import pytest
import requests

from llm.base import LLMUnavailableError
from llm.transcribe import transcribe_audio


def _ok_response(json_body):
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json = Mock(return_value=json_body)
    resp.status_code = 200
    return resp


def test_transcribe_without_api_key_raises_unavailable_no_network_call(monkeypatch):
    # Same leakage concern test_llm.py's Groq tests document: importing
    # webapp.backend triggers load_dotenv(), which can pick up a real
    # local GROQ_API_KEY - clear it explicitly rather than assume absent.
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with patch("llm.transcribe.requests.post") as post:
        with pytest.raises(LLMUnavailableError):
            transcribe_audio(b"fake audio bytes")
    post.assert_not_called()


def test_transcribe_success(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    with patch("llm.transcribe.requests.post") as post:
        post.return_value = _ok_response({"text": "who approves 2.126"})
        result = transcribe_audio(b"fake audio bytes", filename="clip.webm")

    assert result == "who approves 2.126"
    call_kwargs = post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer fake-key"
    assert call_kwargs["files"]["file"][0] == "clip.webm"
    assert call_kwargs["data"]["model"] == "whisper-large-v3-turbo"


def test_transcribe_network_failure_raises_unavailable(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    with patch("llm.transcribe.requests.post", side_effect=requests.Timeout()):
        with pytest.raises(LLMUnavailableError):
            transcribe_audio(b"fake audio bytes")


def test_transcribe_unexpected_response_shape_raises_unavailable(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    with patch("llm.transcribe.requests.post") as post:
        post.return_value = _ok_response({"error": "something else entirely"})
        with pytest.raises(LLMUnavailableError):
            transcribe_audio(b"fake audio bytes")

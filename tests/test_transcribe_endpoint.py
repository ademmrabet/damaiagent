import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from llm.base import LLMUnavailableError
from webapp.backend import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _signup(client, email, password="longenough1"):
    res = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_transcribe_requires_authentication(client):
    res = client.post("/api/transcribe", files={"file": ("clip.webm", io.BytesIO(b"audio"), "audio/webm")})
    assert res.status_code == 401


def test_transcribe_happy_path(client):
    token = _signup(client, "owner@example.com")

    with patch("webapp.backend.transcribe_audio", return_value="who approves 2.126") as mock_transcribe:
        res = client.post(
            "/api/transcribe",
            files={"file": ("clip.webm", io.BytesIO(b"audio"), "audio/webm")},
            headers=_auth(token),
        )

    assert res.status_code == 200
    assert res.json() == {"text": "who approves 2.126"}
    mock_transcribe.assert_called_once()


def test_transcribe_rejects_oversized_recordings(client):
    from webapp.backend import MAX_VOICE_UPLOAD_BYTES

    token = _signup(client, "owner@example.com")
    oversized = io.BytesIO(b"x" * (MAX_VOICE_UPLOAD_BYTES + 1))

    res = client.post(
        "/api/transcribe",
        files={"file": ("clip.webm", oversized, "audio/webm")},
        headers=_auth(token),
    )
    assert res.status_code == 413


def test_transcribe_surfaces_groq_unavailable_as_503(client):
    token = _signup(client, "owner@example.com")

    with patch("webapp.backend.transcribe_audio", side_effect=LLMUnavailableError("GROQ_API_KEY is not set")):
        res = client.post(
            "/api/transcribe",
            files={"file": ("clip.webm", io.BytesIO(b"audio"), "audio/webm")},
            headers=_auth(token),
        )
    assert res.status_code == 503

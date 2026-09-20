"""
Tests for the attachment branch of POST /api/ask (2026-09-20, see
docs/decisions.md) - the part that makes "what's this?" with a file
attached actually read the file, instead of falling through to the
ordinary DAM pipeline with no idea an attachment exists. Mocks
download_attachment/resolve_provider/answer_about_attachment the same
way test_uploads.py and test_transcribe_endpoint.py mock their own
external boundaries, rather than hitting a real bucket or model.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from llm.attachments import UnsupportedAttachmentError
from llm.base import LLMUnavailableError
from webapp.auth import decode_access_token
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


def _attachment_payload(user_id, question="what's this?", **overrides):
    payload = {
        "question": question,
        "attachment": {
            "key": f"attachments/{user_id}/abc123-notes.pdf",
            "content_type": "application/pdf",
            "filename": "notes.pdf",
        },
    }
    payload.update(overrides)
    return payload


def _signup_and_get_id(client, email):
    """/api/auth/me doesn't return a user id, so decode it straight off
    the token this endpoint's own auth gate uses - no need to round-trip
    through some other owned resource just to learn our own id."""
    token = _signup(client, email)
    claims = decode_access_token(token)
    return token, claims["sub"]


def test_attachment_question_requires_authentication(client):
    res = client.post(
        "/api/ask",
        json=_attachment_payload("some-user-id"),
    )
    assert res.status_code == 401


def test_attachment_question_rejects_a_key_belonging_to_someone_else(client):
    token, user_id = _signup_and_get_id(client, "owner@example.com")

    res = client.post(
        "/api/ask",
        json=_attachment_payload("someone-elses-id"),
        headers=_auth(token),
    )
    assert res.status_code == 403


def test_attachment_question_happy_path_text_document(client):
    token, user_id = _signup_and_get_id(client, "owner@example.com")
    fake_provider = Mock(name="groq")
    fake_provider.name = "groq"

    with patch("webapp.backend.resolve_provider", return_value=fake_provider), patch(
        "webapp.backend.download_attachment", return_value=b"2.126 is approved by Sector Manager"
    ), patch(
        "webapp.backend.answer_about_attachment",
        return_value={"text": "Sector Manager approves it.", "provider": "groq"},
    ) as mock_answer:
        res = client.post(
            "/api/ask",
            json=_attachment_payload(user_id, question="who approves this?"),
            headers=_auth(token),
        )

    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == "Sector Manager approves it."
    assert body["source"] == "attachment"
    assert body["used_llm"] is True
    assert body["llm_provider"] == "groq"
    assert body["node_id"] is None
    mock_answer.assert_called_once()
    assert mock_answer.call_args.args[0] == "who approves this?"


def test_attachment_question_off_mode_still_gets_answered(client):
    # "Switch to Auto automatically" (2026-09-20) - an attachment
    # always needs a model, so llm: "off" (or omitted) shouldn't refuse
    # outright the way a plain DAM question would.
    token, user_id = _signup_and_get_id(client, "owner@example.com")
    fake_provider = Mock(name="groq")
    fake_provider.name = "groq"

    def fake_resolve(mode):
        return fake_provider if mode == "auto" else None

    with patch("webapp.backend.resolve_provider", side_effect=fake_resolve), patch(
        "webapp.backend.download_attachment", return_value=b"some text"
    ), patch(
        "webapp.backend.answer_about_attachment",
        return_value={"text": "answer", "provider": "groq"},
    ):
        res = client.post(
            "/api/ask",
            json=_attachment_payload(user_id, llm="off"),
            headers=_auth(token),
        )

    assert res.status_code == 200
    assert res.json()["used_llm"] is True


def test_attachment_question_with_no_provider_available_is_503(client):
    token, user_id = _signup_and_get_id(client, "owner@example.com")

    with patch("webapp.backend.resolve_provider", return_value=None):
        res = client.post(
            "/api/ask",
            json=_attachment_payload(user_id),
            headers=_auth(token),
        )

    assert res.status_code == 503


def test_unsupported_attachment_type_is_returned_as_a_normal_answer_not_an_error(client):
    token, user_id = _signup_and_get_id(client, "owner@example.com")
    fake_provider = Mock(name="groq")
    fake_provider.name = "groq"

    with patch("webapp.backend.resolve_provider", return_value=fake_provider), patch(
        "webapp.backend.download_attachment", return_value=b"binary junk"
    ), patch(
        "webapp.backend.answer_about_attachment",
        side_effect=UnsupportedAttachmentError("Reading spreadsheet attachments isn't supported yet."),
    ):
        res = client.post(
            "/api/ask",
            json=_attachment_payload(user_id),
            headers=_auth(token),
        )

    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "attachment"
    assert body["used_llm"] is False
    assert "spreadsheet" in body["answer"]


def test_attachment_question_surfaces_llm_unavailable_as_503(client):
    token, user_id = _signup_and_get_id(client, "owner@example.com")
    fake_provider = Mock(name="groq")
    fake_provider.name = "groq"

    with patch("webapp.backend.resolve_provider", return_value=fake_provider), patch(
        "webapp.backend.download_attachment", return_value=b"some text"
    ), patch(
        "webapp.backend.answer_about_attachment",
        side_effect=LLMUnavailableError("Groq request failed"),
    ):
        res = client.post(
            "/api/ask",
            json=_attachment_payload(user_id),
            headers=_auth(token),
        )

    assert res.status_code == 503


def test_plain_question_without_attachment_is_unaffected(client):
    # /api/ask stays unauthenticated for ordinary DAM questions - the
    # new auth/ownership gate only applies on the attachment branch.
    res = client.post("/api/ask", json={"question": "who approves 2.126?"})
    assert res.status_code == 200
    assert res.json().get("source") != "attachment"

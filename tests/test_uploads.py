import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

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


FAKE_UPLOAD_RESULT = {
    "key": "attachments/user-1/abc123-notes.pdf",
    "filename": "notes.pdf",
    "content_type": "application/pdf",
    "size": 5,
}


def test_upload_requires_authentication(client):
    res = client.post("/api/uploads", files={"file": ("notes.pdf", io.BytesIO(b"hello"), "application/pdf")})
    assert res.status_code == 401


def test_upload_delegates_to_storage_and_returns_its_metadata(client):
    token = _signup(client, "owner@example.com")

    with patch("webapp.backend.upload_attachment", return_value=FAKE_UPLOAD_RESULT) as mock_upload:
        res = client.post(
            "/api/uploads",
            files={"file": ("notes.pdf", io.BytesIO(b"hello"), "application/pdf")},
            headers=_auth(token),
        )

    assert res.status_code == 200
    assert res.json() == FAKE_UPLOAD_RESULT
    mock_upload.assert_called_once()
    # Second positional arg is the uploader id - confirms the endpoint
    # doesn't accidentally trust a client-supplied user id.
    args, _ = mock_upload.call_args
    assert isinstance(args[1], str) and len(args[1]) > 0


def _post_message_with_attachment(client, token, conversation_id, key=FAKE_UPLOAD_RESULT["key"]):
    return client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "role": "user",
            "text": "see attached",
            "meta": {"attachment": {"key": key, "filename": "notes.pdf", "content_type": "application/pdf", "size": 5}},
        },
        headers=_auth(token),
    )


def test_owner_can_get_a_presigned_url_for_an_attachment_in_their_own_conversation(client):
    token = _signup(client, "owner@example.com")
    conv = client.post("/api/conversations", headers=_auth(token)).json()
    _post_message_with_attachment(client, token, conv["id"])

    with patch("webapp.backend.presign_download", return_value="https://example.test/signed") as mock_presign:
        res = client.get(
            f"/api/conversations/{conv['id']}/attachments/{FAKE_UPLOAD_RESULT['key']}",
            headers=_auth(token),
        )

    assert res.status_code == 200
    assert res.json() == {"url": "https://example.test/signed"}
    mock_presign.assert_called_once_with(FAKE_UPLOAD_RESULT["key"])


def test_unrelated_user_cannot_fetch_an_attachment_url(client):
    owner_token = _signup(client, "owner@example.com")
    other_token = _signup(client, "other@example.com")
    conv = client.post("/api/conversations", headers=_auth(owner_token)).json()
    _post_message_with_attachment(client, owner_token, conv["id"])

    res = client.get(
        f"/api/conversations/{conv['id']}/attachments/{FAKE_UPLOAD_RESULT['key']}",
        headers=_auth(other_token),
    )
    assert res.status_code == 403


def test_shared_with_user_can_still_read_an_attachment_view_only(client):
    # Sharing is view-only for messages (see models.py's ConversationShare
    # docstring) but that's about POSTing - reading an attachment that's
    # already part of the shared history is exactly the kind of read
    # access sharing is meant to grant.
    owner_token = _signup(client, "owner@example.com")
    colleague_token = _signup(client, "colleague@example.com")
    conv = client.post("/api/conversations", headers=_auth(owner_token)).json()
    _post_message_with_attachment(client, owner_token, conv["id"])
    client.post(
        f"/api/conversations/{conv['id']}/share",
        json={"email": "colleague@example.com"},
        headers=_auth(owner_token),
    )

    with patch("webapp.backend.presign_download", return_value="https://example.test/signed"):
        res = client.get(
            f"/api/conversations/{conv['id']}/attachments/{FAKE_UPLOAD_RESULT['key']}",
            headers=_auth(colleague_token),
        )
    assert res.status_code == 200


def test_a_key_never_attached_in_this_conversation_is_a_404_even_for_the_owner(client):
    # This is the guard against a valid, logged-in user trying a key
    # they know about (their own, or a leaked one) against a
    # conversation that never actually referenced it.
    token = _signup(client, "owner@example.com")
    conv = client.post("/api/conversations", headers=_auth(token)).json()
    client.post(
        f"/api/conversations/{conv['id']}/messages",
        json={"role": "user", "text": "no attachment here"},
        headers=_auth(token),
    )

    res = client.get(
        f"/api/conversations/{conv['id']}/attachments/{FAKE_UPLOAD_RESULT['key']}",
        headers=_auth(token),
    )
    assert res.status_code == 404


def test_attachment_url_for_nonexistent_conversation_is_404(client):
    token = _signup(client, "owner@example.com")
    res = client.get(
        f"/api/conversations/does-not-exist/attachments/{FAKE_UPLOAD_RESULT['key']}",
        headers=_auth(token),
    )
    assert res.status_code == 404

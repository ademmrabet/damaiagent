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


def test_new_conversation_starts_empty_and_owned(client):
    token = _signup(client, "owner@example.com")

    res = client.post("/api/conversations", headers=_auth(token))
    assert res.status_code == 200
    body = res.json()
    assert body["messages"] == []
    assert body["title"] == "New chat"
    assert body["is_owner"] is True
    assert body["shared_with"] == []


def test_created_conversation_appears_in_own_list(client):
    token = _signup(client, "owner@example.com")
    created = client.post("/api/conversations", headers=_auth(token)).json()

    res = client.get("/api/conversations", headers=_auth(token))
    assert res.status_code == 200
    body = res.json()
    assert created["id"] in [c["id"] for c in body["own"]]
    assert body["shared_with_me"] == []


def test_appending_a_message_derives_the_title_from_the_first_user_message(client):
    # Mirrors the frontend's own deriveTitle (see useConversations.js) -
    # a real fact worth pinning since this moved server-side with the
    # sharing feature (2026-09-19).
    token = _signup(client, "owner@example.com")
    conv = client.post("/api/conversations", headers=_auth(token)).json()

    res = client.post(
        f"/api/conversations/{conv['id']}/messages",
        json={"role": "user", "text": "who approves the quarterly mission program"},
        headers=_auth(token),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "who approves the quarterly mission program"
    assert body["title_is_default"] is False
    assert len(body["messages"]) == 1

    # A second user message should NOT re-derive the title again.
    res2 = client.post(
        f"/api/conversations/{conv['id']}/messages",
        json={"role": "agent", "text": "Some answer.", "meta": {"nodeId": "2.126"}},
        headers=_auth(token),
    )
    assert res2.json()["title"] == "who approves the quarterly mission program"
    assert len(res2.json()["messages"]) == 2
    assert res2.json()["messages"][1]["meta"]["nodeId"] == "2.126"


def test_long_first_message_gets_truncated_title(client):
    token = _signup(client, "owner@example.com")
    conv = client.post("/api/conversations", headers=_auth(token)).json()

    long_question = "a" * 60
    res = client.post(
        f"/api/conversations/{conv['id']}/messages",
        json={"role": "user", "text": long_question},
        headers=_auth(token),
    )
    title = res.json()["title"]
    # _derive_title keeps MAX_TITLE_LENGTH - 2 chars plus the ellipsis
    # character itself, so the total is one shorter than MAX_TITLE_LENGTH.
    assert len(title) == 41
    assert title.endswith("…")


def test_unrelated_user_cannot_view_a_private_conversation(client):
    owner_token = _signup(client, "owner@example.com")
    other_token = _signup(client, "other@example.com")
    conv = client.post("/api/conversations", headers=_auth(owner_token)).json()

    res = client.get(f"/api/conversations/{conv['id']}", headers=_auth(other_token))
    assert res.status_code == 403


def test_unrelated_user_cannot_post_messages_to_someone_elses_conversation(client):
    owner_token = _signup(client, "owner@example.com")
    other_token = _signup(client, "other@example.com")
    conv = client.post("/api/conversations", headers=_auth(owner_token)).json()

    res = client.post(
        f"/api/conversations/{conv['id']}/messages",
        json={"role": "user", "text": "hi"},
        headers=_auth(other_token),
    )
    assert res.status_code == 403


def test_sharing_with_a_registered_email_grants_read_access(client):
    owner_token = _signup(client, "owner@example.com")
    colleague_token = _signup(client, "colleague@example.com")
    conv = client.post("/api/conversations", headers=_auth(owner_token)).json()
    client.post(
        f"/api/conversations/{conv['id']}/messages",
        json={"role": "user", "text": "who approves 3.111"},
        headers=_auth(owner_token),
    )

    share_res = client.post(
        f"/api/conversations/{conv['id']}/share",
        json={"email": "colleague@example.com"},
        headers=_auth(owner_token),
    )
    assert share_res.status_code == 200
    assert share_res.json()["shared_with"][0]["email"] == "colleague@example.com"

    view_res = client.get(f"/api/conversations/{conv['id']}", headers=_auth(colleague_token))
    assert view_res.status_code == 200
    assert view_res.json()["is_owner"] is False
    assert len(view_res.json()["messages"]) == 1

    list_res = client.get("/api/conversations", headers=_auth(colleague_token))
    assert conv["id"] in [c["id"] for c in list_res.json()["shared_with_me"]]


def test_shared_with_user_still_cannot_post_messages(client):
    # View-only sharing (see models.py's ConversationShare docstring) -
    # access to read is not access to write.
    owner_token = _signup(client, "owner@example.com")
    colleague_token = _signup(client, "colleague@example.com")
    conv = client.post("/api/conversations", headers=_auth(owner_token)).json()
    client.post(
        f"/api/conversations/{conv['id']}/share",
        json={"email": "colleague@example.com"},
        headers=_auth(owner_token),
    )

    res = client.post(
        f"/api/conversations/{conv['id']}/messages",
        json={"role": "user", "text": "trying to post anyway"},
        headers=_auth(colleague_token),
    )
    assert res.status_code == 403


def test_sharing_with_an_unregistered_email_is_a_clear_404(client):
    owner_token = _signup(client, "owner@example.com")
    conv = client.post("/api/conversations", headers=_auth(owner_token)).json()

    res = client.post(
        f"/api/conversations/{conv['id']}/share",
        json={"email": "nobody@example.com"},
        headers=_auth(owner_token),
    )
    assert res.status_code == 404


def test_sharing_with_yourself_is_rejected(client):
    owner_token = _signup(client, "owner@example.com")
    conv = client.post("/api/conversations", headers=_auth(owner_token)).json()

    res = client.post(
        f"/api/conversations/{conv['id']}/share",
        json={"email": "owner@example.com"},
        headers=_auth(owner_token),
    )
    assert res.status_code == 400


def test_sharing_twice_with_the_same_person_does_not_duplicate(client):
    owner_token = _signup(client, "owner@example.com")
    _signup(client, "colleague@example.com")
    conv = client.post("/api/conversations", headers=_auth(owner_token)).json()

    client.post(
        f"/api/conversations/{conv['id']}/share",
        json={"email": "colleague@example.com"},
        headers=_auth(owner_token),
    )
    res = client.post(
        f"/api/conversations/{conv['id']}/share",
        json={"email": "colleague@example.com"},
        headers=_auth(owner_token),
    )
    assert res.status_code == 200
    assert len(res.json()["shared_with"]) == 1


def test_unsharing_revokes_access(client):
    owner_token = _signup(client, "owner@example.com")
    colleague_token = _signup(client, "colleague@example.com")
    conv = client.post("/api/conversations", headers=_auth(owner_token)).json()
    client.post(
        f"/api/conversations/{conv['id']}/share",
        json={"email": "colleague@example.com"},
        headers=_auth(owner_token),
    )

    view_before = client.get(f"/api/conversations/{conv['id']}", headers=_auth(colleague_token))
    assert view_before.status_code == 200

    # Re-sharing (a no-op, per test_sharing_twice_with_the_same_person_does_not_duplicate)
    # is a convenient way to read back the target user's id for the unshare call.
    share_list = client.post(
        f"/api/conversations/{conv['id']}/share",
        json={"email": "colleague@example.com"},
        headers=_auth(owner_token),
    ).json()["shared_with"]
    target_user_id = share_list[0]["user_id"]

    unshare_res = client.delete(
        f"/api/conversations/{conv['id']}/share/{target_user_id}", headers=_auth(owner_token)
    )
    assert unshare_res.status_code == 200
    assert unshare_res.json()["shared_with"] == []

    view_after = client.get(f"/api/conversations/{conv['id']}", headers=_auth(colleague_token))
    assert view_after.status_code == 403


def test_owner_can_delete_their_own_conversation(client):
    token = _signup(client, "owner@example.com")
    conv = client.post("/api/conversations", headers=_auth(token)).json()

    res = client.delete(f"/api/conversations/{conv['id']}", headers=_auth(token))
    assert res.status_code == 200

    get_res = client.get(f"/api/conversations/{conv['id']}", headers=_auth(token))
    assert get_res.status_code == 404


def test_non_owner_cannot_delete_someone_elses_conversation(client):
    owner_token = _signup(client, "owner@example.com")
    other_token = _signup(client, "other@example.com")
    conv = client.post("/api/conversations", headers=_auth(owner_token)).json()

    res = client.delete(f"/api/conversations/{conv['id']}", headers=_auth(other_token))
    assert res.status_code == 403


def test_conversations_endpoints_require_authentication(client):
    res = client.get("/api/conversations")
    assert res.status_code == 401

    res2 = client.post("/api/conversations")
    assert res2.status_code == 401


def test_getting_a_nonexistent_conversation_is_404(client):
    token = _signup(client, "owner@example.com")
    res = client.get("/api/conversations/does-not-exist", headers=_auth(token))
    assert res.status_code == 404

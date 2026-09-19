import pytest
from fastapi.testclient import TestClient

from webapp.auth import _LOGIN_ATTEMPTS
from webapp.backend import app
from webapp.db import SessionLocal
from webapp.models import Role, User


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # The limiter is a plain module-level dict keyed by client IP
    # (see webapp/auth.py) - TestClient always reports the same
    # fake IP ("testclient"), so without resetting this between
    # tests, whichever rate-limit test runs first would poison every
    # later test's login attempts too.
    _LOGIN_ATTEMPTS.clear()
    yield
    _LOGIN_ATTEMPTS.clear()


def test_signup_first_user_becomes_administrator(client):
    res = client.post("/api/auth/signup", json={"email": "first@example.com", "password": "longenough1"})
    assert res.status_code == 200
    assert res.json()["role"] == "administrator"


def test_signup_second_user_becomes_analyst(client):
    client.post("/api/auth/signup", json={"email": "first@example.com", "password": "longenough1"})
    res = client.post("/api/auth/signup", json={"email": "second@example.com", "password": "longenough1"})
    assert res.json()["role"] == "analyst"


def test_signup_rejects_short_password(client):
    res = client.post("/api/auth/signup", json={"email": "a@example.com", "password": "short"})
    assert res.status_code == 400


def test_signup_rejects_duplicate_email(client):
    client.post("/api/auth/signup", json={"email": "dup@example.com", "password": "longenough1"})
    res = client.post("/api/auth/signup", json={"email": "dup@example.com", "password": "somethingelse1"})
    assert res.status_code == 409


def test_signup_rejects_invalid_email(client):
    res = client.post("/api/auth/signup", json={"email": "not-an-email", "password": "longenough1"})
    assert res.status_code == 422


def test_signup_email_is_case_insensitive_for_uniqueness(client):
    client.post("/api/auth/signup", json={"email": "Case@Example.com", "password": "longenough1"})
    res = client.post("/api/auth/signup", json={"email": "case@example.com", "password": "somethingelse1"})
    assert res.status_code == 409


def test_login_succeeds_with_correct_credentials(client):
    client.post("/api/auth/signup", json={"email": "login@example.com", "password": "correctpass1"})
    res = client.post("/api/auth/login", json={"email": "login@example.com", "password": "correctpass1"})
    assert res.status_code == 200
    assert res.json()["access_token"]


def test_login_fails_with_wrong_password(client):
    client.post("/api/auth/signup", json={"email": "login2@example.com", "password": "correctpass1"})
    res = client.post("/api/auth/login", json={"email": "login2@example.com", "password": "wrongpass1"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password"


def test_login_fails_for_nonexistent_account_with_same_generic_message(client):
    # Deliberately the identical message and status as a wrong
    # password (see webapp/backend.py's login()) - a different
    # message here would let this endpoint enumerate valid accounts.
    res = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever1"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password"


def test_login_fails_for_oauth_only_account_with_same_generic_message(client):
    # An account created via Google/Microsoft has no password at all
    # (hashed_password is NULL) - trying to log in with a password
    # anyway must fail the same generic way, not with a different
    # "use Google instead" message that would leak how the account
    # was created.
    db = SessionLocal()
    db.add(User(email="oauthuser@example.com", oauth_provider="google", oauth_sub="abc123", role=Role.analyst))
    db.commit()
    db.close()

    res = client.post("/api/auth/login", json={"email": "oauthuser@example.com", "password": "anything123"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password"


def test_login_rate_limited_after_five_attempts(client):
    client.post("/api/auth/signup", json={"email": "ratelimit@example.com", "password": "correctpass1"})
    for _ in range(5):
        res = client.post("/api/auth/login", json={"email": "ratelimit@example.com", "password": "wrongpass1"})
        assert res.status_code == 401

    res = client.post("/api/auth/login", json={"email": "ratelimit@example.com", "password": "correctpass1"})
    assert res.status_code == 429


def test_me_requires_a_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_rejects_garbage_token(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


def test_me_returns_the_authenticated_account(client):
    signup = client.post(
        "/api/auth/signup",
        json={"email": "me@example.com", "password": "longenough1", "name": "Test User"},
    )
    token = signup.json()["access_token"]

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "me@example.com"
    assert body["name"] == "Test User"
    assert body["role"] == "administrator"


def test_analyst_cannot_reach_admin_only_dashboard(client):
    client.post("/api/auth/signup", json={"email": "admin@example.com", "password": "longenough1"})
    analyst = client.post("/api/auth/signup", json={"email": "analyst@example.com", "password": "longenough1"})
    token = analyst.json()["access_token"]

    res = client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

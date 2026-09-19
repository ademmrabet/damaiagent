import pytest
from fastapi.testclient import TestClient

from webapp.backend import app
from webapp.db import SessionLocal
from webapp.models import Role, User
from webapp.oauth import get_or_create_oauth_user


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_first_oauth_user_becomes_administrator(db):
    user = get_or_create_oauth_user(db, provider="google", subject="sub-1", email="first@example.com", name="First")
    assert user.role == Role.administrator
    assert user.oauth_provider == "google"
    assert user.oauth_sub == "sub-1"
    assert user.hashed_password is None


def test_second_oauth_user_is_a_plain_analyst(db):
    get_or_create_oauth_user(db, provider="google", subject="sub-1", email="first@example.com", name="First")
    second = get_or_create_oauth_user(db, provider="google", subject="sub-2", email="second@example.com", name="Second")
    assert second.role == Role.analyst


def test_same_provider_subject_returns_the_same_row_not_a_duplicate(db):
    first_call = get_or_create_oauth_user(db, provider="google", subject="sub-1", email="a@example.com", name="A")
    second_call = get_or_create_oauth_user(db, provider="google", subject="sub-1", email="a@example.com", name="A")
    assert first_call.id == second_call.id
    assert db.query(User).count() == 1


def test_oauth_login_links_onto_existing_password_account_with_same_email(db):
    # Someone who signed up with a password, then later uses "Sign in
    # with Google" with that same email, should end up as ONE account
    # with both login paths available - not two separate rows.
    existing = User(email="dual@example.com", hashed_password="irrelevant-hash", role=Role.analyst)
    db.add(existing)
    db.commit()
    db.refresh(existing)

    linked = get_or_create_oauth_user(db, provider="google", subject="sub-99", email="dual@example.com", name="Dual")

    assert linked.id == existing.id
    assert linked.oauth_provider == "google"
    assert linked.oauth_sub == "sub-99"
    assert linked.hashed_password == "irrelevant-hash"  # untouched - both paths still work
    assert linked.role == Role.analyst  # pre-existing role preserved, not reset
    assert db.query(User).count() == 1


def test_google_routes_return_503_when_not_configured(client):
    res = client.get("/api/auth/google/login", follow_redirects=False)
    assert res.status_code == 503

    res = client.get("/api/auth/google/callback", follow_redirects=False)
    assert res.status_code == 503


def test_microsoft_routes_return_503_when_not_configured(client):
    res = client.get("/api/auth/microsoft/login", follow_redirects=False)
    assert res.status_code == 503

    res = client.get("/api/auth/microsoft/callback", follow_redirects=False)
    assert res.status_code == 503

import pytest
from fastapi.testclient import TestClient

from webapp.backend import app


@app.get("/api/_test_only/boom")
def _boom():
    raise RuntimeError("something exploded deep in a dependency")


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_unhandled_exception_returns_valid_json_not_plain_text(client):
    res = client.get("/api/_test_only/boom")

    assert res.status_code == 500
    body = res.json()
    assert "detail" in body


def test_unhandled_exception_does_not_leak_the_real_error_text(client):
    res = client.get("/api/_test_only/boom")
    body = res.json()
    assert "exploded" not in body["detail"]
    assert "RuntimeError" not in body["detail"]


def test_ordinary_http_exceptions_are_unaffected(client):
    res = client.post(
        "/api/ask",
        json={
            "question": "hi",
            "attachment": {
                "key": "attachments/someone/x.pdf",
                "content_type": "application/pdf",
                "filename": "x.pdf",
            },
        },
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Not authenticated"

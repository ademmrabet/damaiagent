"""
Tests for the global exception handler added 2026-09-20 (see
docs/decisions.md) - the fix for a PDF upload attempt that surfaced to
Adem as `Unexpected token 'I', "Internal S"... is not valid JSON`.

Root cause: any bare Exception that escapes a route (not raised as an
HTTPException) previously fell through to Starlette's own default
handler, which returns the literal plain-text body "Internal Server
Error" rather than JSON. Every api.js function calls `res.json()`
unconditionally on the response, so that plain-text body surfaced as a
cryptic JSON-parse error instead of any usable message. These tests
register a route that deliberately raises a bare exception and confirm
the app-level handler now always returns valid, generic JSON instead.
"""

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
    # This is the actual assertion that matters: res.json() must not
    # raise. Before the fix, this response body was the literal string
    # "Internal Server Error", which is exactly what broke api.js.
    body = res.json()
    assert "detail" in body


def test_unhandled_exception_does_not_leak_the_real_error_text(client):
    # The generic message is deliberate - the real traceback goes to
    # the server log via logger.exception, not to the client.
    res = client.get("/api/_test_only/boom")
    body = res.json()
    assert "exploded" not in body["detail"]
    assert "RuntimeError" not in body["detail"]


def test_ordinary_http_exceptions_are_unaffected(client):
    # A normal HTTPException (e.g. hitting /api/ask's attachment branch
    # with no token) should still behave exactly as before - the new
    # catch-all only needs to catch what nothing else already handles.
    res = client.post("/api/ask", json={"question": "hi", "attachment": {
        "key": "attachments/someone/x.pdf", "content_type": "application/pdf", "filename": "x.pdf",
    }})
    assert res.status_code == 401
    assert res.json()["detail"] == "Not authenticated"

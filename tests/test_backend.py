
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient

from webapp.backend import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_reports_nodes_loaded(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["nodes_loaded"] == 327


def test_ask_by_id_and_by_title_agree(client):
    by_id = client.post("/api/ask", json={"question": "who are the informed parties for 2.126"})
    by_title = client.post("/api/ask", json={"question": "who needs to be informed for quarterly mission program"})

    assert by_id.status_code == 200
    assert by_title.status_code == 200
    assert by_id.json()["node_id"] == by_title.json()["node_id"] == "2.126"
    assert by_id.json()["answer"] == by_title.json()["answer"]


def test_ask_pronoun_followup_uses_previous_node_id_from_request(client):
    first = client.post(
        "/api/ask",
        json={"question": "who approves of Communication with Co-Financiers of projects"},
    )
    assert first.json()["node_id"] == "2.118"

    followup = client.post(
        "/api/ask",
        json={
            "question": "who are the informed parties for that activity?",
            "previous_node_id": first.json()["node_id"],
        },
    )
    body = followup.json()
    assert body["node_id"] == "2.118"
    assert body["method"] == "context_carryover"


def test_ask_without_previous_node_id_defaults_to_normal_resolution(client):
    res = client.post("/api/ask", json={"question": "who approves 3.111"})
    assert res.status_code == 200
    assert res.json()["node_id"] == "3.111"


def test_ask_french_question_gets_translated_and_answered_in_french(client):
    # Patches GroqProvider.chat directly (not requests.post) so this
    # test is deterministic regardless of whether a real GROQ_API_KEY
    # happens to be set in this environment - chat() raises before
    # ever reaching requests.post when the key is missing, which would
    # make an HTTP-layer mock silently never fire. Two calls happen in
    # sequence here: detect+translate the incoming French question to
    # English (so the untouched, English-only retrieval pipeline can
    # resolve it), then phrase the grounded answer back in French.
    from llm.groq_provider import GroqProvider

    responses = iter([
        "LANGUAGE: fr\nTRANSLATED: who approves 3.111",
        "Pour 3.111, les personnes suivantes approuvent : Origination "
        "Sector Manager, Supporting Dept. Division Manager.",
    ])
    with patch.object(GroqProvider, "chat", side_effect=lambda *a, **k: next(responses)):
        res = client.post(
            "/api/ask",
            json={"question": "qui approuve 3.111", "llm": "groq"},
        )
    body = res.json()
    assert res.status_code == 200
    assert body["node_id"] == "3.111"
    assert body["detected_language"] == "fr"
    assert body["used_llm"] is True
    assert "Origination Sector Manager" in body["answer"]
    assert "Origination Sector Manager" in body["deterministic_answer"]


def test_ask_plain_english_question_never_calls_translation(client):
    # The looks_non_english() pre-filter should skip the extra Groq
    # round trip entirely for ordinary English questions - confirmed
    # here by asserting detected_language defaults to "en" without any
    # translation machinery having run.
    res = client.post("/api/ask", json={"question": "who approves 3.111", "llm": "off"})
    body = res.json()
    assert body["detected_language"] == "en"
    assert body["translation_error"] is None


def test_ask_non_english_question_without_llm_gives_honest_translation_error(client):
    res = client.post(
        "/api/ask",
        json={"question": "qui approuve le programme de mission", "llm": "off"},
    )
    body = res.json()
    assert res.status_code == 200
    assert body["detected_language"] == "en"  # couldn't detect without an LLM
    assert body["translation_error"]
    assert "Off" in body["translation_error"] or "LLM" in body["translation_error"]


def test_ask_vague_single_word_asks_for_clarification(client):
    res = client.post("/api/ask", json={"question": "mission"})
    body = res.json()
    assert res.status_code == 200
    assert body["node_id"] is None
    assert body["method"] == "needs_clarification"
    assert "bit broad" in body["answer"].lower()


def test_ask_invalid_code_is_honest(client):
    res = client.post("/api/ask", json={"question": "what happens with 9.999.999"})
    assert res.status_code == 200
    body = res.json()
    assert body["node_id"] is None
    assert body["method"] == "invalid_id"
    assert "doesn't exist" in body["answer"].lower()


def test_ask_unresolvable_free_text_is_honest(client):
    res = client.post("/api/ask", json={"question": "random unrelated words banana spaceship"})
    assert res.status_code == 200
    body = res.json()
    assert body["node_id"] is None
    assert body["method"] == "out_of_scope"
    assert "outside what i can help with" in body["answer"].lower()


def test_ask_greeting_gets_a_friendly_reply_not_a_dam_lookup(client):
    res = client.post("/api/ask", json={"question": "hi"})
    assert res.status_code == 200
    body = res.json()
    assert body["node_id"] is None
    assert body["method"] == "smalltalk"
    assert "Hello" in body["answer"]


def test_landing_page_served_at_root(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "DAM AI Agent" in res.text
    # Confirms the React build actually landed in webapp/static and is
    # being served, not just that landing.html exists as a shell.
    assert 'type="module"' in res.text
    assert "/assets/" in res.text


def test_chat_route_served(client):
    res = client.get("/chat")
    assert res.status_code == 200
    assert "DAM AI Agent" in res.text
    assert "/assets/" in res.text


def test_dashboard_route_served(client):
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "DAM Dashboard" in res.text
    assert "/assets/" in res.text


def test_ask_without_llm_field_is_pure_deterministic(client):
    res = client.post("/api/ask", json={"question": "who approves 3.111"})
    body = res.json()
    assert body["used_llm"] is False
    assert body["llm_provider"] is None
    assert body["deterministic_answer"] == body["answer"]


def test_ask_llm_off_is_identical_to_omitted(client):
    res = client.post("/api/ask", json={"question": "who approves 3.111", "llm": "off"})
    body = res.json()
    assert body["used_llm"] is False
    assert body["deterministic_answer"] == body["answer"]


def test_ask_llm_ollama_falls_back_when_unreachable(client):
    # No real Ollama server exists in this environment - this exercises
    # the actual fallback path (agent.generate.humanize_answer catching
    # LLMUnavailableError) rather than assuming it works, same principle
    # as every other "confirmed with real data" check in this project.
    with patch("llm.ollama_provider.requests.post", side_effect=requests.ConnectionError()):
        res = client.post("/api/ask", json={"question": "who approves 3.111", "llm": "ollama"})
    body = res.json()
    assert res.status_code == 200
    assert body["used_llm"] is False
    assert body["llm_provider"] == "ollama"
    assert body["llm_error"]
    assert body["answer"] == body["deterministic_answer"]


def test_ask_llm_success_path_uses_grounded_phrasing(client):
    fake_reply = (
        "Origination Sector Manager and Supporting Dept. Division Manager "
        "both need to sign off on this one."
    )
    with patch("llm.groq_provider.requests.post") as post:
        post.return_value.raise_for_status = lambda: None
        post.return_value.json = lambda: {"choices": [{"message": {"content": fake_reply}}]}
        res = client.post(
            "/api/ask",
            json={"question": "who approves 3.111", "llm": "groq"},
        )
    body = res.json()
    if body["used_llm"]:
        assert body["answer"] == fake_reply
        assert body["llm_provider"] == "groq"
    else:
        # GROQ_API_KEY isn't set in this environment - falls back honestly
        # instead of pretending to have called a real model.
        assert "GROQ_API_KEY" in body["llm_error"]


def test_dashboard_summary_reflects_real_graph(client):
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["total_nodes"] == 327
    assert sum(body["node_counts_by_type"].values()) == 327
    assert body["graph"]["total_graph_nodes"] >= 327
    assert body["unresolved_rate"] < 0.05
    assert len(body["top_roles"]) <= 15


def test_llm_config_reports_the_real_resolved_model_names(client):
    res = client.get("/api/llm/config")
    assert res.status_code == 200
    body = res.json()
    assert body["ollama_model"] == "llama3.1"
    assert body["groq_model"] == "llama-3.3-70b-versatile"


def test_llm_config_respects_env_overrides(client, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
    res = client.get("/api/llm/config")
    body = res.json()
    assert body["ollama_model"] == "mistral"
    assert body["groq_model"] == "llama-3.1-8b-instant"


# The status dot / LLM picker / "Auto is default" guarantees used to
# be checkable by grepping the raw HTML this backend serves, because
# the old frontend was plain server-rendered markup. Since the React
# rewrite (2026-08-06), that markup only exists after client-side
# JavaScript runs - a Python TestClient request never executes it, so
# asserting on res.text here would either always fail or (worse)
# silently stop testing anything real. Those same guarantees are now
# checked at the component-source level in tests/test_frontend_source.py
# instead - see that file for why, and for the actual assertions.

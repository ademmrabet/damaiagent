from llm.base import LLMUnavailableError
from agent.generate import build_grounding_prompt, humanize_answer

RESOLVED = {
    "answer": (
        "For 3.111 ('Some Task'), the following approve: "
        "Origination Sector Manager (footnote 3), "
        "Supporting Dept. Division Manager (footnote 4)."
    ),
    "node_id": "3.111",
    "method": "id",
    "score": 1.0,
    "roles": [
        {"role": "Origination Sector Manager", "action": "A", "level": None, "footnote_refs": [3]},
        {"role": "Supporting Dept. Division Manager", "action": "A", "level": None, "footnote_refs": [4]},
    ],
    "node_title": "Some Task",
    "node_type": "task",
    "intent": "approve",
}

NO_MATCH = {
    "answer": "I couldn't find a task in the DAM matching that question.",
    "node_id": None,
    "method": "text_search",
    "score": None,
    "roles": None,
    "node_title": None,
    "node_type": None,
    "intent": None,
}

# A real node was matched (unlike NO_MATCH), but it has no direct
# responsibilities of its own - e.g. a reference-redirect or a
# process-with-children pointer answer. There's nothing to ground an
# LLM rephrasing on here even though node_id is set.
POINTER_ANSWER = {
    "answer": "1.117.2 ('...') redirects to 2.120 ('...'), a process that doesn't carry responsibilities directly. Its activities: 2.121 ('...'), 2.122 ('...').",
    "node_id": "1.117.2",
    "method": "id",
    "score": 1.0,
    "roles": [],
    "node_title": "CSP / RISP Dialogue Mission",
    "node_type": "child_task",
    "intent": "initiate",
}


class FakeProvider:
    name = "fake"

    def __init__(self, response=None, raise_error=None):
        self.response = response
        self.raise_error = raise_error
        self.called = False

    def chat(self, system, user, temperature=0.2, max_tokens=512):
        self.called = True
        if self.raise_error:
            raise self.raise_error
        return self.response


def test_no_provider_returns_deterministic_unchanged():
    result = humanize_answer("who approves 3.111", RESOLVED, None)
    assert result == {
        "text": RESOLVED["answer"],
        "used_llm": False,
        "provider": None,
        "error": None,
    }


def test_no_match_never_calls_the_provider():
    provider = FakeProvider(response="I made something up")
    result = humanize_answer("gibberish query", NO_MATCH, provider)
    assert provider.called is False
    assert result["text"] == NO_MATCH["answer"]
    assert result["used_llm"] is False


def test_pointer_answer_with_a_resolved_node_still_never_calls_the_provider():
    # The gap this guards: node_id IS set here (unlike NO_MATCH), so
    # the old skip condition alone wouldn't have caught this case -
    # roles being empty is what must trigger the skip, or the
    # grounding check would be vacuously true and the LLM could
    # freely rephrase a navigational answer with zero real facts.
    provider = FakeProvider(response="Someone else entirely handles this, trust me.")
    result = humanize_answer("who initiates 1.117.2", POINTER_ANSWER, provider)
    assert provider.called is False
    assert result["text"] == POINTER_ANSWER["answer"]
    assert result["used_llm"] is False


def test_llm_success_when_all_roles_preserved():
    provider = FakeProvider(
        response=(
            "Both the Origination Sector Manager and the Supporting Dept. "
            "Division Manager need to approve this."
        )
    )
    result = humanize_answer("who approves 3.111", RESOLVED, provider)
    assert result["used_llm"] is True
    assert result["provider"] == "fake"
    assert result["error"] is None
    assert result["text"] == provider.response


def test_llm_dropping_a_role_falls_back_to_deterministic():
    provider = FakeProvider(response="Only the Origination Sector Manager approves this.")
    result = humanize_answer("who approves 3.111", RESOLVED, provider)
    assert result["used_llm"] is False
    assert result["text"] == RESOLVED["answer"]
    assert "grounding" in result["error"].lower()


def test_llm_error_falls_back_to_deterministic():
    provider = FakeProvider(raise_error=LLMUnavailableError("connection refused"))
    result = humanize_answer("who approves 3.111", RESOLVED, provider)
    assert result["used_llm"] is False
    assert result["text"] == RESOLVED["answer"]
    assert "connection refused" in result["error"]


def test_llm_empty_response_falls_back():
    provider = FakeProvider(response="   ")
    result = humanize_answer("who approves 3.111", RESOLVED, provider)
    assert result["used_llm"] is False
    assert result["text"] == RESOLVED["answer"]


def test_grounding_prompt_carries_question_facts_and_reference_answer():
    system, user = build_grounding_prompt("who approves 3.111", RESOLVED)
    assert "who approves 3.111" in user
    assert "Origination Sector Manager" in user
    assert "Supporting Dept. Division Manager" in user
    assert "footnote 3" in user or "footnote" in user
    assert RESOLVED["answer"] in user
    assert "ONLY the facts" in system.upper() or "ONLY" in system.upper()


def test_grounding_prompt_no_facts_case():
    system, user = build_grounding_prompt("random query", NO_MATCH)
    assert "no responsibilities recorded" in user

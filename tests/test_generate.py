from llm.base import LLMUnavailableError
from agent.generate import (
    SYSTEM_PROMPT,
    MANY_FACTS_THRESHOLD,
    build_grounding_prompt,
    humanize_answer,
)

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


# Mirrors a real answer with mandatory-notes appended (2026-09-03, see
# docs/decisions.md) - a task with an approve role plus a check/verify
# note plus multiple informed parties easily reaches 4+ facts, the
# exact case MANY_FACTS_THRESHOLD/_LONG_ANSWER_RULE exist for.
MANY_FACTS = {
    "answer": (
        "For 2.126 ('Quarterly Mission program'), the following "
        "approve(s): RDG / Director RDNG. This task must also be "
        "checked/verified by Sector Manager, Supporting Dept. Division "
        "Manager. Concerned Sector VP, RDVP, Task Manager must also be "
        "informed."
    ),
    "node_id": "2.126",
    "method": "id",
    "score": 1.0,
    "roles": [
        {"role": "RDG / Director RDNG", "action": "A", "level": None, "footnote_refs": []},
        {"role": "Sector Manager", "action": "C", "level": None, "footnote_refs": []},
        {"role": "Supporting Dept. Division Manager", "action": "C", "level": None, "footnote_refs": []},
        {"role": "Concerned Sector VP", "action": "( i )", "level": None, "footnote_refs": []},
        {"role": "RDVP", "action": "( i )", "level": None, "footnote_refs": []},
        {"role": "Task Manager", "action": "( i )", "level": None, "footnote_refs": []},
    ],
    "node_title": "Quarterly Mission program",
    "node_type": "task",
    "intent": "approve",
}


# Mirrors a real answer where the mandatory-notes roles (2026-09-03)
# have been split out of what the LLM must reproduce (2026-09-19, see
# docs/decisions.md) - `llm_facts` only has the one role the question
# actually asked about; `roles` still has all 6 (the primary role plus
# the check/verify and informed-party note roles), same as before this
# split existed, so anything still reading the wider `roles` list
# keeps working unchanged.
APPROVE_WITH_NOTES = {
    "answer": (
        "For 2.126 ('Quarterly Mission program'), the following "
        "approve(s): RDG / Director RDNG. This task must also be "
        "checked/verified by Sector Manager, Supporting Dept. Division "
        "Manager. Concerned Sector VP, RDVP, Task Manager/ Task Team "
        "Members must also be informed."
    ),
    "base_answer": (
        "For 2.126 ('Quarterly Mission program'), the following "
        "approve(s): RDG / Director RDNG."
    ),
    "mandatory_notes_text": (
        "This task must also be checked/verified by Sector Manager, "
        "Supporting Dept. Division Manager. Concerned Sector VP, RDVP, "
        "Task Manager/ Task Team Members must also be informed."
    ),
    "node_id": "2.126",
    "method": "id",
    "score": 1.0,
    "roles": [
        {"role": "RDG / Director RDNG", "action": "A", "level": None, "footnote_refs": []},
        {"role": "Sector Manager", "action": "C", "level": None, "footnote_refs": []},
        {"role": "Supporting Dept. Division Manager", "action": "C", "level": None, "footnote_refs": []},
        {"role": "Concerned Sector VP", "action": "( i )", "level": None, "footnote_refs": []},
        {"role": "RDVP", "action": "( i )", "level": None, "footnote_refs": []},
        {"role": "Task Manager/ Task Team Members", "action": "( i )", "level": None, "footnote_refs": []},
    ],
    "llm_facts": [
        {"role": "RDG / Director RDNG", "action": "A", "level": None, "footnote_refs": []},
    ],
    "node_title": "Quarterly Mission program",
    "node_type": "task",
    "intent": "approve",
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


def test_target_language_instruction_is_added_to_the_system_prompt():
    system, _ = build_grounding_prompt("qui approuve 3.111", RESOLVED, target_language="fr")
    assert "French" in system
    # Rule 4 (keep role names/footnote numbers intact) still applies -
    # the language rule is additive, not a replacement.
    assert "footnote" in system.lower()


def test_english_target_language_leaves_the_prompt_unchanged():
    system_en, _ = build_grounding_prompt("who approves 3.111", RESOLVED, target_language="en")
    system_default, _ = build_grounding_prompt("who approves 3.111", RESOLVED)
    assert system_en == system_default == SYSTEM_PROMPT


def test_grounding_check_still_works_when_the_answer_is_in_french():
    # The grounding check (_mentions_expected_facts) looks for the
    # literal English role-name strings regardless of the surrounding
    # sentence's language - this pins that a French answer which
    # correctly preserved the role names (as instructed) still passes.
    provider = FakeProvider(
        response=(
            "Pour 3.111, les personnes suivantes approuvent : "
            "Origination Sector Manager (footnote 3), "
            "Supporting Dept. Division Manager (footnote 4)."
        )
    )
    result = humanize_answer("qui approuve 3.111", RESOLVED, provider, target_language="fr")
    assert result["used_llm"] is True
    assert "Origination Sector Manager" in result["text"]


def test_grounding_check_still_catches_a_dropped_role_in_french():
    # Same guard as the English-only version of this check, just
    # confirming it survives the language change - a French answer
    # that drops a role name should still fail the grounding check and
    # fall back to the safe deterministic answer.
    provider = FakeProvider(
        response="Pour 3.111, Origination Sector Manager approuve."
    )
    result = humanize_answer("qui approuve 3.111", RESOLVED, provider, target_language="fr")
    assert result["used_llm"] is False
    assert result["text"] == RESOLVED["answer"]


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


# Sentence-cap scaling with fact count (2026-09-03, see docs/
# decisions.md) - real gap found live: the mandatory Check/Verify +
# informed-party notes feature routinely pushes real answers to 4-6
# facts, and the original "1-3 sentences" cap put real pressure on the
# model to drop or paraphrase a role name to stay short, which the
# grounding check would then (correctly) reject - so answers with many
# facts kept falling back to the deterministic template far more than
# answers with few facts ever did.
def test_few_facts_keeps_the_short_sentence_cap():
    system, _ = build_grounding_prompt("who approves 3.111", RESOLVED)
    assert "1-3 sentences" in system
    assert len(RESOLVED["roles"]) < MANY_FACTS_THRESHOLD


def test_many_facts_switches_to_the_uncapped_rule():
    system, _ = build_grounding_prompt("who approves 2.126", MANY_FACTS)
    assert "1-3 sentences" not in system
    assert "as many sentences as you need" in system
    assert len(MANY_FACTS["roles"]) >= MANY_FACTS_THRESHOLD


def test_many_facts_answer_succeeds_when_the_llm_states_every_role():
    # The actual point of the feature: a real multi-fact answer that
    # DOES faithfully state every role should now succeed instead of
    # needlessly falling back just because it ran to more sentences.
    provider = FakeProvider(
        response=(
            "RDG / Director RDNG approves this one. It also needs "
            "checking by Sector Manager and Supporting Dept. Division "
            "Manager. Once that's done, Concerned Sector VP, RDVP, and "
            "Task Manager should be kept informed."
        )
    )
    result = humanize_answer("who approves 2.126", MANY_FACTS, provider)
    assert result["used_llm"] is True
    assert result["error"] is None


def test_many_facts_answer_still_fails_grounding_if_a_role_is_dropped():
    # The safety guarantee itself is unchanged - a shorter answer that
    # actually omits one of the six roles still correctly fails,
    # regardless of the relaxed sentence cap.
    provider = FakeProvider(
        response="RDG / Director RDNG approves this, and Sector Manager checks it."
    )
    result = humanize_answer("who approves 2.126", MANY_FACTS, provider)
    assert result["used_llm"] is False
    assert "grounding" in result["error"].lower()


# Whitespace/case-normalized grounding match (2026-09-03) - a model
# introducing trivial formatting noise (double space, different
# capitalization) around an otherwise-faithful role name shouldn't
# trigger a false rejection.
def test_grounding_check_tolerates_incidental_whitespace_and_case_differences():
    provider = FakeProvider(
        response=(
            "origination sector  manager and supporting dept. division "
            "manager both need to approve this."
        )
    )
    result = humanize_answer("who approves 3.111", RESOLVED, provider)
    assert result["used_llm"] is True


def test_grounding_check_still_catches_a_genuinely_different_name():
    # Normalizing whitespace/case must not become a loophole - a role
    # name that's actually wrong (not just differently formatted)
    # still has to fail.
    provider = FakeProvider(response="The Origination Manager approves this one alone.")
    result = humanize_answer("who approves 3.111", RESOLVED, provider)
    assert result["used_llm"] is False


# Grounding-fallback frequency reduction (2026-09-19, see docs/
# decisions.md) - a real screenshot showed a 9-fact answer (1 approve
# role plus 8 check/informed note roles) fail grounding and fall back
# to the template. Splitting the mandatory-notes roles out of what the
# LLM must reproduce is the fix: it only ever needs to preserve the
# roles the question's intent actually matched.
def test_llm_only_needs_to_preserve_the_matched_role_not_the_note_roles():
    provider = FakeProvider(response="RDG / Director RDNG is the one who approves this.")
    result = humanize_answer("who approves 2.126", APPROVE_WITH_NOTES, provider)
    assert result["used_llm"] is True
    assert result["error"] is None


def test_mandatory_notes_are_reattached_verbatim_after_a_successful_rephrase():
    # The LLM's job shrinks to the primary sentence only - the notes
    # text always comes back byte-exact, never at the LLM's mercy.
    provider = FakeProvider(response="RDG / Director RDNG is the one who approves this.")
    result = humanize_answer("who approves 2.126", APPROVE_WITH_NOTES, provider)
    assert result["text"].startswith("RDG / Director RDNG is the one who approves this.")
    assert APPROVE_WITH_NOTES["mandatory_notes_text"] in result["text"]


def test_grounding_prompt_only_lists_the_matched_role_in_english():
    # _facts_block (fed to the LLM) and the grounding check itself
    # should both be scoped to llm_facts on English answers - the note
    # roles never even appear as something the model has to get right.
    _, user = build_grounding_prompt("who approves 2.126", APPROVE_WITH_NOTES)
    assert "RDG / Director RDNG" in user
    assert "Sector Manager" not in user
    assert "Concerned Sector VP" not in user


def test_non_english_answer_still_requires_every_note_role_verbatim():
    # Deliberately NOT split for non-English answers yet -
    # mandatory_notes_text is a fixed English template with no
    # per-language translation, so re-attaching it after a French
    # rephrase would tack an untranslated English sentence onto an
    # otherwise-French answer. A French response that only covers the
    # approve role (mirroring the English-only test above) should
    # still correctly fail grounding here.
    provider = FakeProvider(response="RDG / Director RDNG approuve cela.")
    result = humanize_answer(
        "qui approuve 2.126", APPROVE_WITH_NOTES, provider, target_language="fr"
    )
    assert result["used_llm"] is False
    assert result["text"] == APPROVE_WITH_NOTES["answer"]


# A real role name in this DAM's own extracted data has no space
# before its slash ("Task Manager/ Task Team Members" - a raw-PDF-
# extraction artifact, not a meaningful fact). Its own dedicated
# fixture, scoped so the slash-spaced role is actually in `llm_facts`
# and required by the grounding check - APPROVE_WITH_NOTES doesn't
# exercise this since its one llm_fact ("RDG / Director RDNG") already
# has consistent spacing.
INITIATE_WITH_SLASH_ROLE = {
    "answer": "For 2.111 ('...'), the following initiate(s): Task Manager/ Task Team Members.",
    "base_answer": "For 2.111 ('...'), the following initiate(s): Task Manager/ Task Team Members.",
    "mandatory_notes_text": "",
    "node_id": "2.111",
    "method": "id",
    "score": 1.0,
    "roles": [
        {"role": "Task Manager/ Task Team Members", "action": "I", "level": None, "footnote_refs": []},
    ],
    "llm_facts": [
        {"role": "Task Manager/ Task Team Members", "action": "I", "level": None, "footnote_refs": []},
    ],
    "node_title": "...",
    "node_type": "task",
    "intent": "initiate",
}


def test_grounding_check_tolerates_inconsistent_slash_spacing():
    # An LLM naturally "cleaning up" the missing space before the slash
    # while writing fluent prose shouldn't fail grounding over pure
    # formatting noise, not an actual dropped or altered fact.
    provider = FakeProvider(response="Task Manager / Task Team Members initiates this one.")
    result = humanize_answer("who initiates 2.111", INITIATE_WITH_SLASH_ROLE, provider)
    assert result["used_llm"] is True


def test_grounding_check_still_catches_a_real_change_around_the_slash():
    # The slash-spacing tolerance must not become a loophole for an
    # actually different name.
    provider = FakeProvider(response="Task Manager and Team initiates this one.")
    result = humanize_answer("who initiates 2.111", INITIATE_WITH_SLASH_ROLE, provider)
    assert result["used_llm"] is False

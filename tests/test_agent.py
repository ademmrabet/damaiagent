import pytest

from modeling.build_nodes import build_nodes
from modeling.graph import build_graph
from knowledge.search import build_search_index
from agent.qa import answer_question
from agent.authority import detect_intent
from tests.fixtures.known_cases import PDF_PATH


@pytest.fixture(scope="module")
def setup():
    nodes = build_nodes(PDF_PATH)
    graph, _ = build_graph(nodes)
    vectorizer, matrix, searchable_ids = build_search_index(nodes)
    return nodes, graph, vectorizer, matrix, searchable_ids


def test_id_phrased_and_title_phrased_questions_give_same_answer(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    by_id = answer_question(
        "who are the informed parties for 2.126",
        nodes, graph, vectorizer, matrix, searchable_ids
    )
    by_title = answer_question(
        "who needs to be informed for quarterly mission program",
        nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert by_id["node_id"] == by_title["node_id"] == "2.126"
    assert by_id["answer"] == by_title["answer"]


def test_approve_question_matches_screenshot(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves 3.111", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert "Origination Sector Manager" in result["answer"]
    assert "Supporting Dept. Division Manager" in result["answer"]


# Mandatory Check/Verify + informed-party notes (2026-09-03, see docs/
# decisions.md) - domain rule from Adem: when a task has a recorded
# Check/Verify entity, that step is mandatory, so it should surface on
# ANY narrow answer about that task, not just when someone explicitly
# asks "who checks this." 2.126 is a real node with both a Check (C)
# role, several action types, and informed-party roles, verified
# directly against answer_question's real output before writing these
# assertions - not fabricated node data.
def test_approve_answer_also_surfaces_the_mandatory_check_and_informed_notes(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves 2.126", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert "RDG" in result["answer"]  # the actual approve answer, unchanged
    assert "must also be checked/verified by" in result["answer"]
    assert "Sector Manager (HQ-based / Region-based)" in result["answer"]
    assert "must also be informed" in result["answer"]
    assert "Concerned Sector VP" in result["answer"]
    # The mandatory-note roles are real facts now, not just answer
    # text - they have to be in "roles" too, or an LLM rephrasing could
    # silently drop them without the grounding check catching it.
    role_names = {r["role"] for r in result["roles"]}
    assert "Sector Manager (HQ-based / Region-based)" in role_names
    assert "Concerned Sector VP" in role_names


def test_check_intent_answer_does_not_redundantly_repeat_its_own_note(setup):
    # "who checks 2.126" already answers WITH the check/verify roles as
    # its main sentence - the mandatory-note appendix should skip
    # repeating them a second time, only adding the (different)
    # informed-party note.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who checks 2.126", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert "check(s) / verifie(s): Sector Manager" in result["answer"]
    assert "must also be checked/verified by" not in result["answer"]
    assert "must also be informed" in result["answer"]


def test_informed_question_has_no_redundant_informed_note(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who are the informed parties for 2.126",
        nodes, graph, vectorizer, matrix, searchable_ids,
    )

    assert "must also be checked/verified by" in result["answer"]
    assert "must also be informed" not in result["answer"]


def test_consult_intent_never_matches_bare_c_or_check(setup):
    intent = detect_intent("who consults on this")
    assert intent["name"] == "consult"
    assert intent["matches"]("C", None) is False
    assert intent["matches"]("C1", 1) is False
    assert intent["matches"]("C3", 3) is True
    assert intent["matches"]("C4", 4) is True


def test_check_intent_never_matches_consult_codes(setup):
    intent = detect_intent("who checks this")
    assert intent["name"] == "check"
    assert intent["matches"]("C", None) is True
    assert intent["matches"]("C1", 1) is True
    assert intent["matches"]("C3", 3) is False


def test_invalid_code_is_honest_not_fabricated_and_never_answers_a_different_task(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "what happens with 9.999.999", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] is None
    assert result["method"] == "invalid_id"
    assert "doesn't exist" in result["answer"].lower()
    assert "9.999.999" in result["answer"]


def test_unresolvable_free_text_query_is_honest_not_fabricated(setup):
    # Updated 2026-08-06: this query has real, substantive content
    # words ("unrelated", "banana", "spaceship") that share nothing
    # with the DAM's vocabulary - now gets the more explicit
    # out-of-scope message instead of the vaguer "couldn't find a
    # task" (see agent/qa.py's docstring on the not-resolution-matches
    # branch for why these two cases are now told apart).
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "random unrelated words banana spaceship",
        nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] is None
    assert result["method"] == "out_of_scope"
    assert "outside what i can help with" in result["answer"].lower()


def test_greeting_never_touches_the_dam_lookup_pipeline(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question("hi", nodes, graph, vectorizer, matrix, searchable_ids)

    assert result["node_id"] is None
    assert result["method"] == "smalltalk"
    assert "Hello" in result["answer"]


def test_invalid_code_in_real_chapter_suggests_real_siblings_not_a_random_task(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves 3.999", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] is None
    assert result["method"] == "invalid_id"
    assert "3.999" in result["answer"]
    assert "Did you mean" in result["answer"]


def test_process_match_points_to_children_not_dead_end(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "organization of nso missions", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] == "3.110"
    assert "3.111" in result["answer"]


def test_reference_redirect_to_a_process_points_to_its_children(setup):
    # The real bug Adem found: 1.117.2's own row carries no
    # responsibilities - the DAM just says "See 2.120: Organization of
    # mission". Before the reference-pointer fix, this dead-ended in
    # "no one is recorded to initiate" even though 2.120's own child
    # tasks (2.121-2.126) plainly do have initiators.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who initiates 1.117.2", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] == "1.117.2"
    assert result["roles"] == []
    assert "redirects to 2.120" in result["answer"]
    assert "2.121" in result["answer"]
    assert "no one is recorded" not in result["answer"].lower()


def test_reference_redirect_to_a_task_with_direct_responsibilities(setup):
    # 1.115.1 redirects to TWO real tasks (1.114.1 / 1.114.2), and
    # those tasks DO carry their own responsibilities directly (unlike
    # 2.120, which only has responsibilities on its children) - the
    # pointer should surface those facts, not another children list.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who initiates 1.115.1", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] == "1.115.1"
    assert "redirects to 1.114.1" in result["answer"]
    assert "Country Economist" in result["answer"]


def test_typo_in_intent_keyword_still_resolves_to_the_right_intent_and_answer(setup):
    # Real gap Adem found: an id-shaped query with a misspelled intent
    # verb ("aproves") still resolved the right node (id matching is
    # typo-immune, it's just a digit pattern) but silently lost the
    # intent filter, dumping every responsibility on the task instead
    # of just the approvers - looked like it worked, was actually
    # quietly less useful than what was asked.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    typo_result = answer_question(
        "who aproves 2.126", nodes, graph, vectorizer, matrix, searchable_ids
    )
    clean_result = answer_question(
        "who approves 2.126", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert typo_result["intent"] == "approve"
    assert typo_result["answer"] == clean_result["answer"]


def test_typo_in_free_text_query_still_resolves_the_right_node(setup):
    # No id in the query at all, AND both content words misspelled -
    # exercises the TF-IDF-side correction (knowledge/search.py), not
    # just the intent-keyword-side correction.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who aproves the qaurterly mision program",
        nodes, graph, vectorizer, matrix, searchable_ids,
    )

    assert result["node_id"] == "2.126"
    assert result["intent"] == "approve"


def test_consult_vs_check_precision_unaffected_by_typo_correction(setup):
    # Confirms typo correction only ever changes WHICH intent gets
    # selected - it can't reopen the "bare C is Check, not Consult"
    # ambiguity that was already carefully fixed, since correction
    # never touches the actual action-code matching rules.
    consult = detect_intent("who consults on this")
    check = detect_intent("who checks this")
    assert consult["matches"]("C", None) is False
    assert consult["matches"]("C3", 3) is True
    assert check["matches"]("C", None) is True
    assert check["matches"]("C3", 3) is False


def test_genuinely_unrelated_query_is_still_honestly_unresolved(setup):
    # The real false positive found while building this: "unrelated"
    # (correctly spelled) was getting "corrected" into "related" (a
    # real DAM-vocabulary word) purely by textual similarity, turning
    # a query that should honestly fail into a confident wrong answer.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "random unrelated words banana spaceship",
        nodes, graph, vectorizer, matrix, searchable_ids,
    )

    assert result["node_id"] is None


def test_pronoun_followup_carries_over_previous_node_not_a_lookalike_title(setup):
    # The real bug Adem found live: 2.118 ("Communication with
    # Co-Financiers of projects") and 3.226 ("Communication with
    # Co-Financiers of projects and third parties") are two DIFFERENT
    # nodes with near-identical titles. A first question correctly
    # resolves 2.118 by title match; the natural chat follow-up "who
    # are the informed parties for that activity?" names no subject of
    # its own - its only real content word, "parties", happens to
    # overlap with 3.226's title instead, and text search alone landed
    # there at a comfortably "confident" 0.42 score. previous_node_id
    # should override that and keep the conversation on 2.118.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    first = answer_question(
        "who approves of Communication with Co-Financiers of projects",
        nodes, graph, vectorizer, matrix, searchable_ids,
    )
    assert first["node_id"] == "2.118"

    followup = answer_question(
        "who are the informed parties for that activity?",
        nodes, graph, vectorizer, matrix, searchable_ids,
        previous_node_id=first["node_id"],
    )

    assert followup["node_id"] == "2.118"
    assert followup["method"] == "context_carryover"
    assert followup["intent"] == "informed"


def test_differently_worded_pronoun_free_followup_also_carries_over(setup):
    # The fixed-phrase-list version of this fix (first attempt) was
    # immediately defeated by this exact live rewording: no "that
    # activity", no "it" - just "and who are the informed partie?".
    # It resolved to the same wrong node (3.226) at the identical 0.42
    # score as the original bug, proving the phrase list was never the
    # real signal - the score gap was. This pins the score-based fix
    # against the specific wording that broke the first attempt.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    first = answer_question(
        "who approves of Communication with Co-Financiers of projects",
        nodes, graph, vectorizer, matrix, searchable_ids,
    )
    assert first["node_id"] == "2.118"

    followup = answer_question(
        "and who are the informed partie?",
        nodes, graph, vectorizer, matrix, searchable_ids,
        previous_node_id=first["node_id"],
    )

    assert followup["node_id"] == "2.118"
    assert followup["method"] == "context_carryover"


def test_strong_fresh_match_overrides_previous_context(setup):
    # A follow-up that DOES name a real, distinctive subject of its
    # own should win on its own merits, not get swept into carryover
    # just because a previous_node_id exists.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves the quarterly mission program",
        nodes, graph, vectorizer, matrix, searchable_ids,
        previous_node_id="2.118",
    )

    assert result["node_id"] == "2.126"
    assert result["method"] == "text_search"


def test_followup_with_its_own_explicit_id_ignores_previous_context(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves 3.111",
        nodes, graph, vectorizer, matrix, searchable_ids,
        previous_node_id="2.118",
    )

    assert result["node_id"] == "3.111"
    assert result["method"] == "id"


def test_action_code_followup_never_gets_swallowed_by_context_carryover(setup):
    # The real live bug this was built for (2026-09-03, see docs/
    # decisions.md): asking "what's I, A and (i)?" right after a task
    # question got silently absorbed by the context-carryover fallback
    # instead of answering the actual question - the bare letters are
    # too short to count as "real content words" (_content_word_count
    # strips anything under 3 characters), so it looked exactly like
    # an under-specified follow-up about the same task. The action-
    # code detector has to run and short-circuit BEFORE context-
    # carryover ever gets a chance to fire, or this regresses silently.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    first = answer_question(
        "who approves 2.126", nodes, graph, vectorizer, matrix, searchable_ids
    )
    assert first["node_id"] == "2.126"

    followup = answer_question(
        "what's I, A and (i)?",
        nodes, graph, vectorizer, matrix, searchable_ids,
        previous_node_id=first["node_id"],
    )

    assert followup["node_id"] is None
    assert followup["method"] == "action_code_legend"
    assert "Initiate" in followup["answer"]
    assert "Approve" in followup["answer"]
    assert "informed" in followup["answer"].lower()


def test_pronoun_followup_with_no_previous_context_falls_through_normally(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who are the informed parties for that activity?",
        nodes, graph, vectorizer, matrix, searchable_ids,
        previous_node_id=None,
    )

    assert result["method"] != "context_carryover"


def test_single_ambiguous_word_asks_for_clarification_instead_of_guessing(setup):
    # Real gap the professor flagged: a new employee with no idea about
    # the DAM tends to type something this short. "mission" alone
    # scores close across three genuinely different real tasks (2.121,
    # 2.124, 2.125) - the old behavior silently picked the top one and
    # answered as if certain, which is a guess dressed up as an answer.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "mission", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] is None
    assert result["method"] == "needs_clarification"
    assert "2.12" in result["answer"]  # one of the real close candidates


def test_bare_intent_verb_with_no_subject_asks_for_clarification(setup):
    # "approve" alone names an action but no activity - even though
    # resolve_query only finds one candidate for it, that candidate
    # isn't something the user actually specified.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "approve", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] is None
    assert result["method"] == "needs_clarification"


def test_well_specified_question_is_unaffected_by_the_clarification_gate(setup):
    # A real, well-formed question with a clear, dominant winner should
    # never get swept into "needs clarification" just because it's
    # short in word count.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves the quarterly mission program",
        nodes, graph, vectorizer, matrix, searchable_ids,
    )

    assert result["node_id"] == "2.126"
    assert result["method"] == "text_search"


def test_help_recognizes_new_employee_phrasings_not_just_the_word_help(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    for phrasing in ["i'm new here", "how does this work", "where do i start"]:
        result = answer_question(
            phrasing, nodes, graph, vectorizer, matrix, searchable_ids
        )
        assert result["method"] == "smalltalk"
        assert "Delegation of Authority Matrix" in result["answer"]


def test_reference_entirely_out_of_document_scope_says_so_honestly(setup):
    # Adem's real screenshot: 2.312.2's row on the actual DAM page is
    # just "See DAM 16.100, 16.200, 16.300, and 16.400" spanning the
    # whole row - chapter 16 isn't part of this ~79-page export at
    # all. Before this fix, that fell all the way through to the
    # generic "no one is recorded to check" message, which reads as
    # "the DAM has no answer" when the DAM actually gives an explicit
    # one - it's just not included in this document.
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who checks 2.312.2", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] == "2.312.2"
    assert "16.100" in result["answer"]
    assert "16.400" in result["answer"]
    assert "outside the scope" in result["answer"].lower()
    assert "no one is recorded" not in result["answer"].lower()

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
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "random unrelated words banana spaceship",
        nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] is None
    assert "couldn't find" in result["answer"].lower()


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

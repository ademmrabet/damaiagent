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
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
    )
    by_title = answer_question(
        "who needs to be informed for quarterly mission program",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
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


def test_approve_answer_also_surfaces_the_mandatory_check_and_informed_notes(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves 2.126", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert "RDG" in result["answer"]
    assert "must also be checked/verified by" in result["answer"]
    assert "Sector Manager (HQ-based / Region-based)" in result["answer"]
    assert "must also be informed" in result["answer"]
    assert "Concerned Sector VP" in result["answer"]
    role_names = {r["role"] for r in result["roles"]}
    assert "Sector Manager (HQ-based / Region-based)" in role_names
    assert "Concerned Sector VP" in role_names


def test_check_intent_answer_does_not_redundantly_repeat_its_own_note(setup):
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
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
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


def test_invalid_code_is_honest_not_fabricated_and_never_answers_a_different_task(
    setup,
):
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
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
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
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who initiates 1.115.1", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] == "1.115.1"
    assert "redirects to 1.114.1" in result["answer"]
    assert "Country Economist" in result["answer"]


def test_typo_in_intent_keyword_still_resolves_to_the_right_intent_and_answer(setup):
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
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who aproves the qaurterly mision program",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
    )

    assert result["node_id"] == "2.126"
    assert result["intent"] == "approve"


def test_consult_vs_check_precision_unaffected_by_typo_correction(setup):
    consult = detect_intent("who consults on this")
    check = detect_intent("who checks this")
    assert consult["matches"]("C", None) is False
    assert consult["matches"]("C3", 3) is True
    assert check["matches"]("C", None) is True
    assert check["matches"]("C3", 3) is False


def test_genuinely_unrelated_query_is_still_honestly_unresolved(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "random unrelated words banana spaceship",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
    )

    assert result["node_id"] is None


def test_pronoun_followup_carries_over_previous_node_not_a_lookalike_title(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    first = answer_question(
        "who approves of Communication with Co-Financiers of projects",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
    )
    assert first["node_id"] == "2.118"

    followup = answer_question(
        "who are the informed parties for that activity?",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
        previous_node_id=first["node_id"],
    )

    assert followup["node_id"] == "2.118"
    assert followup["method"] == "context_carryover"
    assert followup["intent"] == "informed"


def test_differently_worded_pronoun_free_followup_also_carries_over(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    first = answer_question(
        "who approves of Communication with Co-Financiers of projects",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
    )
    assert first["node_id"] == "2.118"

    followup = answer_question(
        "and who are the informed partie?",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
        previous_node_id=first["node_id"],
    )

    assert followup["node_id"] == "2.118"
    assert followup["method"] == "context_carryover"


def test_strong_fresh_match_overrides_previous_context(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves the quarterly mission program",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
        previous_node_id="2.118",
    )

    assert result["node_id"] == "2.126"
    assert result["method"] == "text_search"


def test_followup_with_its_own_explicit_id_ignores_previous_context(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves 3.111",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
        previous_node_id="2.118",
    )

    assert result["node_id"] == "3.111"
    assert result["method"] == "id"


def test_action_code_followup_never_gets_swallowed_by_context_carryover(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    first = answer_question(
        "who approves 2.126", nodes, graph, vectorizer, matrix, searchable_ids
    )
    assert first["node_id"] == "2.126"

    followup = answer_question(
        "what's I, A and (i)?",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
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
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
        previous_node_id=None,
    )

    assert result["method"] != "context_carryover"


def test_single_ambiguous_word_asks_for_clarification_instead_of_guessing(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "mission", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] is None
    assert result["method"] == "needs_clarification"
    assert "2.12" in result["answer"]


def test_bare_intent_verb_with_no_subject_asks_for_clarification(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "approve", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] is None
    assert result["method"] == "needs_clarification"


def test_well_specified_question_is_unaffected_by_the_clarification_gate(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves the quarterly mission program",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
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


def test_full_dump_answer_shows_action_names_not_bare_letter_codes(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "tell me about 2.111", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] == "2.111"
    assert "Initiate (I):" in result["answer"]
    assert "Approve (A):" in result["answer"]
    assert "Informed:" in result["answer"]
    assert "  I:" not in result["answer"]
    assert "  A:" not in result["answer"]


def test_bare_single_letter_followup_with_no_other_subject_is_recognized(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    first = answer_question(
        "who approves 2.126", nodes, graph, vectorizer, matrix, searchable_ids
    )
    assert first["node_id"] == "2.126"

    followup = answer_question(
        "what I means ?",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
        previous_node_id=first["node_id"],
    )

    assert followup["node_id"] is None
    assert followup["method"] == "action_code_legend"
    assert "Initiate" in followup["answer"]


def test_answer_with_mandatory_notes_exposes_llm_facts_narrower_than_roles(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves 2.126", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["llm_facts"] == [
        r for r in result["roles"] if r["role"] == "RDG / Director RDNG"
    ]
    assert len(result["llm_facts"]) < len(result["roles"])
    assert "must also be checked/verified by" in result["mandatory_notes_text"]
    assert "must also be informed" in result["mandatory_notes_text"]
    assert result["base_answer"] in result["answer"]
    assert result["mandatory_notes_text"] in result["answer"]


def test_no_intent_answer_has_no_split_llm_facts(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "tell me about 2.111", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["intent"] is None
    assert result["llm_facts"] is None
    assert result["mandatory_notes_text"] == ""
    assert result["base_answer"] == result["answer"]


def test_reference_entirely_out_of_document_scope_says_so_honestly(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who checks 2.312.2", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["node_id"] == "2.312.2"
    assert "16.100" in result["answer"]
    assert "16.400" in result["answer"]
    assert "outside the scope" in result["answer"].lower()
    assert "no one is recorded" not in result["answer"].lower()


def test_out_of_scope_question_is_not_carried_over_to_previous_task(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    first = answer_question(
        "who approves 2.126",
        nodes,
        graph,
        vectorizer,
        matrix,
        searchable_ids,
    )

    for question in (
        "who is the president of the AfDB",
        "who approves of the journey in dahdah",
    ):
        result = answer_question(
            question,
            nodes,
            graph,
            vectorizer,
            matrix,
            searchable_ids,
            previous_node_id=first["node_id"],
        )
        assert result["method"] != "context_carryover"
        assert result["node_id"] is None

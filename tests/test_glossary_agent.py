import pytest

from agent.glossary import (
    detect_glossary_query,
    format_glossary_answer,
    expand_acronym_in_role_name,
    lookup_term,
)
from modeling.build_nodes import build_nodes
from modeling.graph import build_graph
from knowledge.search import build_search_index
from agent.qa import answer_question
from tests.fixtures.known_cases import PDF_PATH


def test_lookup_term_is_case_insensitive():
    assert lookup_term("ddg") == lookup_term("DDG") == lookup_term("Ddg")


def test_lookup_term_returns_none_for_unknown_term():
    assert lookup_term("NOTAREALCODE") is None


@pytest.mark.parametrize("query", [
    "what does DDG mean",
    "what does DDG stand for",
    "what does DDG stand For?",
    "what does DDG stands for",  # real query Adem tried live - grammatically
    "what does DDG stands for?",  # off ("stands" not "stand") but very natural
    "what does the acronym DDG mean",
    "define DDG",
    "what is the meaning of DDG",
    "what's DDG?",
    "what's DDG",
    "whats DDG",
    "what is DDG",
])
def test_glossary_trigger_phrasings_all_detect_the_same_term(query):
    detection = detect_glossary_query(query)
    assert detection is not None
    assert detection["term"] == "DDG"
    assert detection["found"] is not None


def test_rdng_resolves_via_manual_alias_even_though_its_not_in_the_pdf_list():
    # Real gap Adem hit live: "RDNG" appears directly in DAM role names
    # ("RDG / Director RDNG") but the Abbreviations pages (2-7) never
    # define it as its own entry - only "RDG" is defined there. Added
    # as a hand-written MANUAL_ALIASES entry (agent/glossary.py) since
    # it's a real term the DAM uses, not a parsing bug to fix.
    found = lookup_term("RDNG")
    assert found is not None
    assert "Nigeria" in found[1]


def test_rdng_reachable_through_the_full_detection_and_formatting_path():
    detection = detect_glossary_query("what does RDNG stands for?")
    assert detection is not None
    assert detection["found"] is not None
    answer = format_glossary_answer(detection)
    assert "RDNG stands for" in answer


@pytest.mark.parametrize("query", [
    "who approves 2.120",
    "what is 2.120",
    "who initiates the mission program",
    "hello",
    "what is the mission program",
    "what's XYZQ",  # bare form + unresolved term: falls through, not an honest "not found"
])
def test_ordinary_dam_questions_never_trigger_the_glossary_path(query):
    # The glossary trigger phrasing is deliberately narrow so it never
    # intercepts a normal DAM-task question - especially "what is X",
    # which would otherwise collide with real id lookups.
    assert detect_glossary_query(query) is None


def test_format_glossary_answer_for_a_known_term():
    detection = {"term": "DDG", "found": ("DDG", "Deputy Director-General")}
    answer = format_glossary_answer(detection)
    assert "DDG" in answer
    assert "Deputy Director-General" in answer


def test_format_glossary_answer_for_an_unknown_term_is_honest_not_fabricated():
    detection = {"term": "NOTAREALCODE", "found": None}
    answer = format_glossary_answer(detection)
    assert "isn't in the DAM" in answer
    assert "NOTAREALCODE" in answer


def test_expand_acronym_in_role_name_for_a_bare_acronym_role():
    seen = set()
    result = expand_acronym_in_role_name("DDG", seen)
    assert result == "DDG (Deputy Director-General)"


def test_expand_acronym_in_role_name_for_a_composite_role():
    seen = set()
    result = expand_acronym_in_role_name("Country Manager / DDG", seen)
    assert result == "Country Manager / DDG (DDG = Deputy Director-General)"


def test_expand_acronym_in_role_name_only_expands_once_per_answer():
    seen = set()
    first = expand_acronym_in_role_name("DDG", seen)
    second = expand_acronym_in_role_name("DDG", seen)
    assert "(Deputy Director-General)" in first
    assert second == "DDG"


def test_expand_acronym_in_role_name_leaves_unknown_role_untouched():
    seen = set()
    assert expand_acronym_in_role_name("Country Economist", seen) == "Country Economist"


@pytest.fixture(scope="module")
def setup():
    nodes = build_nodes(PDF_PATH)
    graph, _ = build_graph(nodes)
    vectorizer, matrix, searchable_ids = build_search_index(nodes)
    return nodes, graph, vectorizer, matrix, searchable_ids


def test_glossary_query_answered_end_to_end_through_answer_question(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "what does DDG mean", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["method"] == "glossary"
    assert result["node_id"] is None
    assert "Deputy Director-General" in result["answer"]


def test_unknown_glossary_term_answered_honestly_end_to_end(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "what does XYZQ mean", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["method"] == "glossary_not_found"
    assert result["node_id"] is None
    assert "isn't in the DAM" in result["answer"]


def test_dam_task_question_still_reaches_the_normal_pipeline_not_glossary(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves 1.114.1", nodes, graph, vectorizer, matrix, searchable_ids
    )

    assert result["method"] == "id"
    assert result["node_id"] == "1.114.1"


def test_role_list_answer_inline_expands_a_known_acronym_role(setup):
    nodes, graph, vectorizer, matrix, searchable_ids = setup

    result = answer_question(
        "who approves 1.114.1", nodes, graph, vectorizer, matrix, searchable_ids
    )

    # 1.114.1's real approvers include CODE (Committee on Development
    # Effectiveness) - confirmed via responsible_roles() before writing
    # this test.
    assert "CODE (Committee on Development Effectiveness)" in result["answer"]

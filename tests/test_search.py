import pytest

from modeling.build_nodes import build_nodes
from knowledge.search import build_search_index, resolve_query, find_ids_in_query
from tests.fixtures.known_cases import PDF_PATH


@pytest.fixture(scope="module")
def index():
    nodes = build_nodes(PDF_PATH)
    vectorizer, matrix, searchable_ids = build_search_index(nodes)
    return nodes, vectorizer, matrix, searchable_ids


def test_literal_id_in_query_short_circuits_to_id_method(index):
    nodes, vectorizer, matrix, searchable_ids = index

    result = resolve_query(
        "who approves 2.513.3.a", nodes, vectorizer, matrix, searchable_ids
    )

    assert result["method"] == "id"
    assert result["matches"] == [{"id": "2.513.3.a", "score": 1.0}]


def test_fake_looking_number_not_treated_as_id(index):
    nodes, _, _, _ = index
    assert find_ids_in_query("give me 99.999.999 please", nodes) == []


def test_exact_title_text_match_ranks_first(index):
    nodes, vectorizer, matrix, searchable_ids = index

    result = resolve_query(
        "quarterly mission program", nodes, vectorizer, matrix, searchable_ids
    )

    assert result["method"] == "text_search"
    assert result["matches"][0]["id"] == "2.126"
    assert result["matches"][0]["score"] == pytest.approx(1.0)


def test_process_titles_are_searchable(index):
    nodes, vectorizer, matrix, searchable_ids = index

    result = resolve_query(
        "organization of nso missions", nodes, vectorizer, matrix, searchable_ids
    )

    assert result["matches"][0]["id"] == "3.110"
    assert nodes["3.110"].node_type == "process"


def test_unrelated_query_returns_no_matches(index):
    nodes, vectorizer, matrix, searchable_ids = index

    result = resolve_query(
        "random unrelated words banana spaceship",
        nodes, vectorizer, matrix, searchable_ids
    )

    assert result["matches"] == []


def test_id_shaped_but_nonexistent_code_does_not_fall_through_to_text_search(index):
    # The core bug this guards: "9.999.999" is shaped like a DAM id but
    # isn't one. Before this fix, resolve_query would silently treat
    # the whole query as free text and could confidently return some
    # UNRELATED real task by shared vocabulary. It must instead say
    # the code doesn't exist, never guess at a different task.
    nodes, vectorizer, matrix, searchable_ids = index

    result = resolve_query(
        "what happens with 9.999.999", nodes, vectorizer, matrix, searchable_ids
    )

    assert result["method"] == "invalid_id"
    assert result["invalid_id"] == "9.999.999"
    assert result["matches"] == []


def test_invalid_code_in_a_real_chapter_suggests_siblings(index):
    nodes, vectorizer, matrix, searchable_ids = index

    # 3.999 doesn't exist, but chapter 3 (NSO) very much does - the
    # suggestions should come from real chapter-3 tasks/processes.
    result = resolve_query(
        "who approves 3.999", nodes, vectorizer, matrix, searchable_ids
    )

    assert result["method"] == "invalid_id"
    assert result["invalid_id"] == "3.999"
    assert len(result["suggestions"]) > 0
    for s in result["suggestions"]:
        assert s["id"].split(".")[0] == "3"


def test_invalid_code_in_a_nonexistent_chapter_falls_back_to_text_suggestions(index):
    nodes, vectorizer, matrix, searchable_ids = index

    result = resolve_query(
        "who approves the quarterly mission program 9.999",
        nodes, vectorizer, matrix, searchable_ids
    )

    assert result["method"] == "invalid_id"
    assert result["invalid_id"] == "9.999"
    # chapter 9 doesn't exist, so suggestions must come from the
    # leftover descriptive words instead - "quarterly mission program"
    # should surface 2.126 even though the code itself was bogus.
    assert any(s["id"] == "2.126" for s in result["suggestions"])

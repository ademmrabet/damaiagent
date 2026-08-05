import pdfplumber
import pytest

from extraction.table_extractor import extract_words
from parsing.rows import build_rows, ordered_lines
from parsing.task_blocks import build_task_blocks
from parsing.hierarchy import get_identifier
from parsing.metadata import extract_title, extract_references

from parsing.hierarchy import get_node_type, get_parent_task_id

from tests.fixtures.known_cases import (
    CASES,
    PDF_PATH,
    THRESHOLD_VARIANT_PAGE_INDEX,
    THRESHOLD_VARIANT_PARENT,
    THRESHOLD_VARIANT_IDS,
)


def _blocks_by_id(page_index):
    pdf = pdfplumber.open(PDF_PATH)
    page = pdf.pages[page_index]
    lines = ordered_lines(build_rows(extract_words(page)))
    blocks = build_task_blocks(lines)

    return {
        get_identifier(b["text"]): b["text"]
        for b in blocks
        if get_identifier(b["text"])
    }


@pytest.mark.parametrize(
    "task_id",
    [tid for tid, c in CASES.items() if c["status"] == "fixed"]
)
def test_title_matches_expected(task_id):
    case = CASES[task_id]
    blocks = _blocks_by_id(case["page_index"])

    raw = blocks.get(task_id)
    assert raw is not None, f"{task_id} not found on page {case['page_index']}"

    title = extract_title(raw, task_id)
    assert title == case["expected_title"]


def test_2312_2_references_extracted():
    case = CASES["2.312.2"]
    blocks = _blocks_by_id(case["page_index"])
    raw = blocks["2.312.2"]

    refs = extract_references(raw)
    assert refs == case["expected_references"]


def test_3225_range_reference_extracted_and_expanded():
    case = CASES["3.225"]
    blocks = _blocks_by_id(case["page_index"])
    raw = blocks["3.225"]

    assert extract_title(raw, "3.225") == case["expected_title"]
    assert extract_references(raw) == case["expected_references"]


def test_3226_title_not_stolen_by_3225():
    case = CASES["3.226"]
    blocks = _blocks_by_id(case["page_index"])
    raw = blocks["3.226"]

    assert extract_title(raw, "3.226") == case["expected_title"]


@pytest.mark.parametrize("task_id", ["1.115.1", "1.115.2", "1.117.1", "1.117.2"])
def test_see_id_references_extracted_from_real_pages(task_id):
    case = CASES[task_id]
    blocks = _blocks_by_id(case["page_index"])
    raw = blocks[task_id]

    assert extract_title(raw, task_id) == case["expected_title"]
    assert extract_references(raw) == case["expected_references"]


@pytest.mark.parametrize("task_id", ["1.114.1", "1.114.2"])
def test_hyphen_suffixed_digit_survives_title_extraction(task_id):
    # Real regression: "3-Year Rolling Business Plan" was coming out
    # as "-Year Rolling Business Plan" - the digit before a hyphen was
    # being stripped as if it were a footnote number.
    case = CASES[task_id]
    blocks = _blocks_by_id(case["page_index"])
    raw = blocks[task_id]

    title = extract_title(raw, task_id)
    assert title == case["expected_title"]
    assert "3-Year" in title


def test_threshold_variant_ids_reconstructed():
    blocks = _blocks_by_id(THRESHOLD_VARIANT_PAGE_INDEX)

    for variant_id in THRESHOLD_VARIANT_IDS:
        assert variant_id in blocks, f"{variant_id} not found"
        assert get_parent_task_id(variant_id) == THRESHOLD_VARIANT_PARENT
        assert get_node_type(variant_id) == "threshold_variant"

    assert THRESHOLD_VARIANT_PARENT in blocks
    assert get_node_type(THRESHOLD_VARIANT_PARENT) == "child_task"


@pytest.mark.parametrize("variant_id,expected_title", [
    ("2.513.3.a", "Up to UA 2,000,000"),
    ("2.513.3.c", "Over UA 10,000,000"),
])
def test_threshold_variant_titles_are_clean(variant_id, expected_title):
    blocks = _blocks_by_id(THRESHOLD_VARIANT_PAGE_INDEX)
    raw = blocks[variant_id]
    assert extract_title(raw, variant_id) == expected_title


@pytest.mark.xfail(reason=(
    "NOTE_PATTERN's comma-adjacency fix only catches comma-formatted "
    "amounts (2,000,000). '2 million' / '10 million' are plain "
    "space-separated digits with no comma and no other distinguishing "
    "text signal, so they still get stripped as false footnote "
    "numbers. This needs real superscript/geometry detection (v1's "
    "original approach for footnote markers) to fix properly, not "
    "another text-pattern special case."
))
def test_threshold_variant_2513_3b_needs_geometry():
    blocks = _blocks_by_id(THRESHOLD_VARIANT_PAGE_INDEX)
    raw = blocks["2.513.3.b"]
    assert extract_title(raw, "2.513.3.b") == "Over UA 2 million up to UA 10 million"



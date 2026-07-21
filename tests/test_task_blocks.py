import pdfplumber
import pytest

from extraction.table_extractor import extract_words
from parsing.rows import build_rows, ordered_lines
from parsing.task_blocks import build_task_blocks
from parsing.hierarchy import get_identifier
from parsing.metadata import extract_title, extract_references

from tests.fixtures.known_cases import CASES, PDF_PATH


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


@pytest.mark.xfail(reason="needs geometry/x-position, deferred to normalize stage")
def test_2126_title_needs_geometry():
    case = CASES["2.126"]
    blocks = _blocks_by_id(case["page_index"])
    raw = blocks.get("2.126", "")

    title = extract_title(raw, "2.126")
    assert title == case["expected_title"]

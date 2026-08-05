import pdfplumber
import pytest

from extraction.table_extractor import extract_words
from parsing.rows import build_rows, ordered_lines
from parsing.task_blocks import build_task_blocks
from parsing.hierarchy import get_identifier
from parsing.metadata import extract_title
from parsing.action_geometry import extract_action_instances, extract_informed_instances

from tests.fixtures.known_cases import (
    PDF_PATH,
    ROW_SPLIT_PAGE_INDEX,
    ROW_SPLIT_EXPECTED,
    ROW_SPLIT_EXPECTED_FOOTNOTES,
    HYPHEN_DIGIT_PAGE_INDEX,
    HYPHEN_DIGIT_CASES,
)


@pytest.fixture(scope="module")
def page_58_blocks():
    pdf = pdfplumber.open(PDF_PATH)
    page = pdf.pages[ROW_SPLIT_PAGE_INDEX]
    words = extract_words(page)
    chars = page.chars
    lines = ordered_lines(build_rows(words))
    blocks = build_task_blocks(lines)
    return {
        get_identifier(b["text"]): b
        for b in blocks
        if get_identifier(b["text"])
    }, chars, words


@pytest.mark.parametrize("task_id", list(ROW_SPLIT_EXPECTED.keys()))
def test_row_split_actions_match_screenshot(page_58_blocks, task_id):
    blocks, chars, words = page_58_blocks
    block = blocks[task_id]

    actions = extract_action_instances(
        block["text"], chars, words, block["top"], block["bottom"]
    )
    informed = extract_informed_instances(chars, block["top"], block["bottom"])

    found = sorted(
        (i["action"], i["level"]) for i in actions + informed
    )
    expected = sorted(ROW_SPLIT_EXPECTED[task_id])

    assert found == expected, f"{task_id}: expected {expected}, got {found}"

    found_footnotes = sorted(fn for i in actions for fn in i["footnote_refs"])
    assert found_footnotes == sorted(ROW_SPLIT_EXPECTED_FOOTNOTES[task_id])


@pytest.mark.parametrize("task_id,expected_title", list(HYPHEN_DIGIT_CASES.items()))
def test_hyphen_adjacent_digits_not_stripped(page_58_blocks, task_id, expected_title):
    blocks, _, _ = page_58_blocks
    block = blocks[task_id]
    assert extract_title(block["text"], task_id) == expected_title

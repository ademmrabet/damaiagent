import pdfplumber
import pytest

from extraction.table_extractor import extract_characters
from parsing.column_roles import extract_column_headers

from tests.fixtures.known_cases import PDF_PATH

CORRUPTED_PAGE_INDEX = 43

MULTI_DIRECTOR_PAGE_INDEX = 26


@pytest.fixture(scope="module")
def page_43_headers():
    pdf = pdfplumber.open(PDF_PATH)
    chars = extract_characters(pdf.pages[CORRUPTED_PAGE_INDEX])
    return [h["role"] for h in extract_column_headers(chars)]


def test_no_character_interleaving(page_43_headers):
    assert not any("CRoIuSntMr" in role for role in page_43_headers)


def test_rism_and_country_manager_are_separate_columns(page_43_headers):
    assert "Regional Implementation Support Manager (RISM)" in page_43_headers
    assert "Country Manager / DDG" in page_43_headers

    combined = "Regional Implementation Support Manager (RISM) Country Manager / DDG"
    assert combined not in page_43_headers


def test_four_director_roles_not_merged():
    pdf = pdfplumber.open(PDF_PATH)
    chars = extract_characters(pdf.pages[MULTI_DIRECTOR_PAGE_INDEX])
    roles = [h["role"] for h in extract_column_headers(chars)]

    expected = [
        "Director, Safeguards & Compliance (SNSC)",
        "Director, Resources Mobilisation & Partnerships (FIRM)",
        "Director, Syndications & Client Solutions (FIST)",
    ]
    for role in expected:
        assert role in roles

    assert not any("Safeguards" in r and "Syndications" in r for r in roles)


def test_no_empty_headers():
    pdf = pdfplumber.open(PDF_PATH)
    for page in pdf.pages:
        chars = extract_characters(page)
        headers = extract_column_headers(chars)
        assert all(h["role"].strip() for h in headers)


def test_footnote_digit_stripped_from_role_headers():
    pdf = pdfplumber.open(PDF_PATH)
    roles = set()
    for page_index in [58, 60, 64, 67, 69]:
        headers = extract_column_headers(extract_characters(pdf.pages[page_index]))
        for h in headers:
            if "Regional NSO Lead" in h["role"]:
                roles.add(h["role"])

    assert roles == {"Regional NSO Lead"}


def test_multi_digit_footnote_fully_stripped():
    pdf = pdfplumber.open(PDF_PATH)
    for page_index in [52, 53, 75]:
        headers = extract_column_headers(extract_characters(pdf.pages[page_index]))
        for h in headers:
            assert not h["role"].rstrip() or not h["role"].rstrip()[-1].isdigit() or "." in h["role"], (
                f"page {page_index}: {h['role']!r} still ends in an unstripped digit"
            )


def test_department_codes_with_periods_not_stripped():
    pdf = pdfplumber.open(PDF_PATH)
    all_roles = set()
    for page in pdf.pages:
        for h in extract_column_headers(extract_characters(page)):
            all_roles.add(h["role"])

    for expected in ["Manager FIFC.4", "Manager FITR.2", "Manager PGCL.1"]:
        assert expected in all_roles


def test_full_document_duplicate_responsibilities_stay_low():
    from modeling.build_nodes import build_nodes

    nodes = build_nodes(PDF_PATH)

    duplicate_count = 0
    for node in nodes.values():
        seen = set()
        for r in node.responsibilities:
            key = (r.role, r.action, r.level, tuple(r.footnote_refs))
            if key in seen:
                duplicate_count += 1
            seen.add(key)

    assert duplicate_count <= 5

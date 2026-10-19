import pytest
import pdfplumber

from parsing.glossary import extract_abbreviations, build_abbreviation_glossary
from tests.fixtures.known_cases import (
    PDF_PATH,
    ABBREVIATIONS_FIRST_PAGE_INDEX,
    ABBREVIATIONS_LAST_PAGE_INDEX,
    KNOWN_ABBREVIATIONS,
)


@pytest.fixture(scope="module")
def glossary():
    with pdfplumber.open(PDF_PATH) as pdf:
        return build_abbreviation_glossary(
            pdf, ABBREVIATIONS_FIRST_PAGE_INDEX, ABBREVIATIONS_LAST_PAGE_INDEX
        )


def test_known_terms_are_extracted_with_the_exact_expected_definition(glossary):
    for term, expected_definition in KNOWN_ABBREVIATIONS.items():
        assert term in glossary
        assert glossary[term] == expected_definition


def test_def_only_continuation_row_is_not_dropped_as_an_empty_entry(glossary):
    assert "Concerned VP / Manager" in glossary
    assert "Concerned VP" not in glossary


def test_page_footer_page_number_is_not_leaked_into_a_definition(glossary):
    for definition in glossary.values():
        words = definition.split()
        assert not (
            len(words) >= 2
            and words[-1] in ("xiv", "xv", "xvi", "xvii", "xviii", "xix")
        )


def test_section_header_row_is_not_captured_as_a_fake_entry():
    with pdfplumber.open(PDF_PATH) as pdf:
        entries = extract_abbreviations(pdf.pages[2])
    terms = [e["term"] for e in entries]
    assert "Committees of" not in terms


def test_no_duplicate_term_has_conflicting_case(glossary):
    upper_counts = {}
    for term in glossary:
        upper_counts.setdefault(term.upper(), []).append(term)
    for upper, variants in upper_counts.items():
        assert len(set(variants)) == 1, f"{upper} has case variants: {variants}"


def test_boilerplate_page_title_is_never_captured_as_an_entry(glossary):
    lowered_terms = [t.lower() for t in glossary]
    assert not any("alphabetical order" in t for t in lowered_terms)
    assert not any("abbreviations and acronyms" == t for t in lowered_terms)


def test_glossary_section_pages_are_deliberately_out_of_scope():
    assert ABBREVIATIONS_FIRST_PAGE_INDEX == 2
    assert ABBREVIATIONS_LAST_PAGE_INDEX == 7

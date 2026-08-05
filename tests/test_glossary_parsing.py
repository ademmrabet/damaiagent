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
    # Real bug: "Concerned VP" (term-only row) followed by its
    # definition on the NEXT row (def-only, no new term) was wrongly
    # treated as "start a brand new term-less entry", which then got
    # silently filtered out for having an empty definition, while the
    # wrapped term continuation ("/ Manager") landed on the wrong
    # entry instead. Fixed by treating a def-only row as a
    # continuation of the current entry's definition, not a new entry.
    assert "Concerned VP / Manager" in glossary
    assert "Concerned VP" not in glossary


def test_page_footer_page_number_is_not_leaked_into_a_definition(glossary):
    # Real bug: a lone lowercase roman numeral page number (xiv, xv,
    # xvi...) at the bottom of each page landed close enough in `top`
    # to the last real row that it got folded into that row's
    # definition text, e.g. "NSO and Private Sector Support Department
    # xv" instead of "...Department".
    for definition in glossary.values():
        words = definition.split()
        assert not (len(words) >= 2 and words[-1] in ("xiv", "xv", "xvi", "xvii", "xviii", "xix"))


def test_section_header_row_is_not_captured_as_a_fake_entry():
    # Real bug: "Committees of the Board of Directors:" (a section
    # header, not a term/definition pair) has term-column text
    # ("Committees of") AND definition-column text ("the Board of
    # Directors:") on the same row, so the old term-only colon-skip
    # check never caught it. Fixed by also skipping rows whose
    # definition-column text ends in ":".
    with pdfplumber.open(PDF_PATH) as pdf:
        entries = extract_abbreviations(pdf.pages[2])
    terms = [e["term"] for e in entries]
    assert "Committees of" not in terms


def test_no_duplicate_term_has_conflicting_case(glossary):
    # Sanity check on the merge step: term keys should be the
    # PDF's own casing, not accidentally split into two entries by
    # case (e.g. "ddg" vs "DDG").
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
    # Documented, deliberate limitation (see docs/decisions.md): the
    # Glossary section's long multi-line definitions let its term and
    # definition columns drift out of row alignment, so
    # extract_abbreviations() is only ever run against pages 2-7 by
    # build_abbreviation_glossary() - never pages 8-11. This test just
    # pins that scoping decision so it can't silently regress.
    assert ABBREVIATIONS_FIRST_PAGE_INDEX == 2
    assert ABBREVIATIONS_LAST_PAGE_INDEX == 7

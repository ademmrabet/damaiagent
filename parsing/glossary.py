import re
from collections import defaultdict

BOILERPLATE_MARKERS = (
    "internal use",
    "usage interne",
    "in alphabetical order",
    "abbreviations and acronyms",
)

TOP_MERGE_TOLERANCE = 3.0
TITLE_FONT_SIZE_MIN = 20
TERM_COLUMN_MAX_X0 = 145

# Every one of these pages ends with a lone lower-case roman numeral
# (the page footer's own page number, e.g. "xiv", "xv", "xvi" ... in
# strict page order across pages 2-7) landing close enough in `top` to
# the last real definition row on the page that TOP_MERGE_TOLERANCE
# folds it into that row's text - confirmed by checking that these
# trailing tokens form an unbroken page-number sequence, not real
# content. Stripped as a final cleanup pass rather than filtered at
# the row level, since it's cheaper and more precise than trying to
# exclude the footer at cluster time (which risks also cutting real
# single-word defs).
_ROMAN_NUMERAL_WORD = re.compile(
    r"^m{0,4}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$"
)


def _strip_page_footer_artifact(definition):
    words = definition.split()
    if len(words) >= 2 and _ROMAN_NUMERAL_WORD.match(words[-1]) and words[-1].islower():
        return " ".join(words[:-1])
    return definition


def _rows_from_words(words):
    """
    Groups words into visual rows by `top`, merging rows whose `top`
    values are within TOP_MERGE_TOLERANCE of each other.

    Confirmed against real page data before writing this: on these
    pages, a term and its definition are sometimes rendered ~1pt apart
    in `top` (e.g. "APPR" at top=215, its definition "Annual Portfolio
    Performance Review" at top=214) rather than perfectly aligned -
    without this tolerance they'd wrongly be treated as two unrelated
    rows. Genuinely separate lines (a term wrapping onto its own next
    line, e.g. "Concerned VP" / "/ Manager", 5-11pt apart) stay
    separate, since normal line spacing on these pages is ~13-17pt,
    well outside this tolerance.
    """
    buckets = defaultdict(list)
    for w in words:
        buckets[round(w["top"], 1)].append(w)

    tops = sorted(buckets)
    clustered_tops = []
    current_group = []
    for top in tops:
        if current_group and top - current_group[-1] <= TOP_MERGE_TOLERANCE:
            current_group.append(top)
        else:
            if current_group:
                clustered_tops.append(current_group)
            current_group = [top]
    if current_group:
        clustered_tops.append(current_group)

    rows = []
    for group in clustered_tops:
        row_words = []
        for top in group:
            row_words.extend(buckets[top])
        row_words.sort(key=lambda w: w["x0"])
        rows.append(row_words)
    return rows


def _is_boilerplate(text):
    lowered = text.lower()
    return any(marker in lowered for marker in BOILERPLATE_MARKERS)


def extract_abbreviations(page, term_max_x0=TERM_COLUMN_MAX_X0):
    """
    Parses one page of the DAM's "Abbreviations and Acronyms" section
    (a two-column code/definition list, term column on the left) into
    a list of {"term": str, "definition": str} entries.

    Scoped deliberately to the short-definition Abbreviations section,
    not the longer-form Glossary a few pages later (page 8 on) - the
    Glossary's definitions routinely wrap across many lines, which
    lets its term and definition columns drift out of row-alignment
    with each other over the course of a page (confirmed by checking:
    the term-column reading order for the Abbreviations pages stays
    alphabetical throughout, but the same check on the Glossary pages
    does not, e.g. "Annual Programming..." reads between "ADF Charter"
    and "AfDB Charter" instead of after both). Reconstructing a
    reliably-ordered term sequence for the Glossary would need real
    column text-flow analysis, not a per-row pairing like this one -
    deferred, not attempted here, since it isn't what was actually
    needed (defining acronyms like DDG/RDG/RISM, which live entirely
    in the Abbreviations section).
    """
    words = [
        w for w in page.extract_words(extra_attrs=["size"])
        if w["size"] < TITLE_FONT_SIZE_MIN
    ]
    rows = _rows_from_words(words)

    entries = []
    current = None

    for row_words in rows:
        term_words = [w["text"] for w in row_words if w["x0"] < term_max_x0]
        def_words = [w["text"] for w in row_words if w["x0"] >= term_max_x0]

        term_text = " ".join(term_words)
        def_text = " ".join(def_words)
        full_text = " ".join(w["text"] for w in row_words)

        if _is_boilerplate(full_text) or def_text.strip().endswith(":"):
            continue

        if term_words and def_words:
            # A fresh term arriving alongside definition text is what
            # actually starts a new entry - NOT "any row with
            # definition-column text", which would wrongly treat a
            # definition that simply wraps onto its own line (no new
            # term on it) as a brand new, term-less entry.
            if current:
                entries.append(current)
            current = {"term": term_text, "definition": def_text}
        elif term_words:
            if term_text.endswith(":"):
                continue
            if current:
                current["term"] = (current["term"] + " " + term_text).strip()
            else:
                current = {"term": term_text, "definition": ""}
        elif def_words:
            if current:
                current["definition"] = (current["definition"] + " " + def_text).strip()

    if current:
        entries.append(current)

    for entry in entries:
        entry["definition"] = _strip_page_footer_artifact(entry["definition"])

    return [e for e in entries if e["term"] and e["definition"]]


def build_abbreviation_glossary(pdf, first_page_index, last_page_index):
    """
    Runs extract_abbreviations() across the given inclusive page-index
    range and merges the results into one {term: definition} dict.

    The source document lists a handful of terms twice across these
    pages (confirmed: EDCC, ECC, EMT, OCC, PEN, ECGF, PIVP, PINS - real
    repeats in the DAM's own text, not a parsing artifact), sometimes
    with slightly different wording between the two listings (e.g.
    PINS: "NSO and Private Sector Support Department" vs "NSO &
    Private Sector Support"). Keeps the LONGER of the two definitions
    per term, on the assumption that the more detailed listing is more
    useful for a "what does X mean" lookup - both are correct, this is
    just a tie-break, not a correctness fix.
    """
    merged = {}
    for i in range(first_page_index, last_page_index + 1):
        for entry in extract_abbreviations(pdf.pages[i]):
            term = entry["term"]
            definition = entry["definition"]
            if term not in merged or len(definition) > len(merged[term]):
                merged[term] = definition
    return merged

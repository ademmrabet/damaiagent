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

_ROMAN_NUMERAL_WORD = re.compile(
    r"^m{0,4}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$"
)


# drop the page number (roman numeral) glued to the last definition
def _strip_page_footer_artifact(definition):
    words = definition.split()
    if len(words) >= 2 and _ROMAN_NUMERAL_WORD.match(words[-1]) and words[-1].islower():
        return " ".join(words[:-1])
    return definition


# group words into rows for one glossary page
def _rows_from_words(words):
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


# true for header/footer text that is not a definition
def _is_boilerplate(text):
    lowered = text.lower()
    return any(marker in lowered for marker in BOILERPLATE_MARKERS)


# read one page of the acronyms list into term and definition pairs
def extract_abbreviations(page, term_max_x0=TERM_COLUMN_MAX_X0):
    words = [
        w
        for w in page.extract_words(extra_attrs=["size"])
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


# merge the acronym pages into one glossary dict
def build_abbreviation_glossary(pdf, first_page_index, last_page_index):
    merged = {}
    for i in range(first_page_index, last_page_index + 1):
        for entry in extract_abbreviations(pdf.pages[i]):
            term = entry["term"]
            definition = entry["definition"]
            if term not in merged or len(definition) > len(merged[term]):
                merged[term] = definition
    return merged

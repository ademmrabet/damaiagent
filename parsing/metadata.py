import re

from parsing.text_cleaning import clean

ACTION_PATTERN = re.compile(r"\(\s*i\s*\)" r"|\bI\b" r"|\b[CRA]\d*\b")

NOTE_PATTERN = re.compile(r"(?<![,-])\b\d{1,3}\b(?![,-])")

REFERENCE_PATTERN = re.compile(r"See\s+DAM\s+([\d.,\sand]+)", re.IGNORECASE)

RANGE_REFERENCE_PATTERN = re.compile(
    r"Refer\s+to\s+Activit(?:y|ies)\s+"
    r"(\d+(?:\.\d+)+)"
    r"(?:\s*[-–]\s*(\d+(?:\.\d+)+))?"
    r"\s+in\s+Section\s+\d+\.?",
    re.IGNORECASE,
)

SEE_ID_COLON_PATTERN = re.compile(r"\bSee\s+(\d+(?:\.\d+)+)\s*:", re.IGNORECASE)

SEE_ID_SLASH_PATTERN = re.compile(
    r"\(\s*See\s+(\d+(?:\.\d+)+)\s*/\s*(\d+(?:\.\d+)+)\s*\)", re.IGNORECASE
)

REFERENCE_ID_PATTERN = re.compile(r"\d+(?:\.\d+)+")


# turn a range like 2.114 to 2.117 into every id in it
def _expand_id_range(start_id, end_id):

    start_parts = start_id.split(".")
    end_parts = end_id.split(".")

    if start_parts[:-1] != end_parts[:-1]:
        return [start_id, end_id]

    try:
        start_n = int(start_parts[-1])
        end_n = int(end_parts[-1])
    except ValueError:
        return [start_id, end_id]

    prefix = ".".join(start_parts[:-1])

    return [f"{prefix}.{n}" for n in range(start_n, end_n + 1)]


VALID_ACTIONS = {
    "I",
    "I1",
    "I2",
    "I3",
    "C",
    "C1",
    "C2",
    "C3",
    "C4",
    "R",
    "R1",
    "R2",
    "A",
    "A1",
    "A2",
    "A3",
    "( i )",
}


# remove the id from the start of the text
def strip_identifier(text, identifier):
    if identifier and text.startswith(identifier):
        return text[len(identifier) :]

    return re.sub(r"^\d+(?:\.\d+)+", "", text)


# ids mentioned after 'see', including lists and ranges
def extract_references(text):

    if not text:
        return []

    references = []

    for match in REFERENCE_PATTERN.finditer(text):
        for ref_id in REFERENCE_ID_PATTERN.findall(match.group(1)):
            if ref_id not in references:
                references.append(ref_id)

    for match in RANGE_REFERENCE_PATTERN.finditer(text):

        start_id, end_id = match.group(1), match.group(2)
        ids = _expand_id_range(start_id, end_id) if end_id else [start_id]

        for ref_id in ids:
            if ref_id not in references:
                references.append(ref_id)

    for match in SEE_ID_COLON_PATTERN.finditer(text):
        ref_id = match.group(1)
        if ref_id not in references:
            references.append(ref_id)

    for match in SEE_ID_SLASH_PATTERN.finditer(text):
        for ref_id in match.groups():
            if ref_id not in references:
                references.append(ref_id)

    return references


# cut out 'see 2.120' style phrases
def remove_references(text):

    if not text:
        return ""

    text = REFERENCE_PATTERN.sub("", text)
    text = RANGE_REFERENCE_PATTERN.sub("", text)
    text = SEE_ID_SLASH_PATTERN.sub("", text)
    text = SEE_ID_COLON_PATTERN.sub("", text)

    return text


# find the action codes (A, C, R, I...) in the text
def extract_actions(text):
    if not text:
        return []

    text = clean(text)
    text = re.sub(r"\bI(\d+)\b", "I", text)

    clean_actions = []

    for action in ACTION_PATTERN.findall(text):

        if action in VALID_ACTIONS:
            clean_actions.append(action)

        elif len(action) >= 2 and action[0] in {"I", "C", "R", "A"}:
            clean_actions.append(action[0])

    return clean_actions


# remove action codes from the text
def remove_actions(text):
    if not text:
        return ""

    return ACTION_PATTERN.sub("", text)


# find footnote numbers in the text
def extract_note_references(text, identifier=None):
    if not text:
        return []

    text = clean(text)
    text = strip_identifier(text, identifier)
    text = remove_references(text)

    notes = NOTE_PATTERN.findall(text)

    for action in ACTION_PATTERN.findall(text):

        if (
            action not in VALID_ACTIONS
            and len(action) >= 2
            and action[0] in {"I", "C", "R", "A"}
        ):
            fused_note = action[1:]

            if fused_note.isdigit():
                notes.append(fused_note)

    unique_notes = []

    for n in notes:
        if n not in unique_notes:
            unique_notes.append(n)

    return unique_notes


# remove footnote numbers from the text
def remove_note_references(text):
    if not text:
        return ""

    return NOTE_PATTERN.sub("", text)


WORD_BOUNDARY_CORRUPTION_PATTERN = re.compile(r"[a-z][A-Z]")


# true when spacing in the text looks broken by the pdf extraction
def looks_word_boundary_corrupted(text):
    return bool(text) and bool(WORD_BOUNDARY_CORRUPTION_PATTERN.search(text))


# what is left of the text once id, actions and notes are removed
def extract_title(text, identifier=None):
    if not text:
        return ""

    text = clean(text)
    text = re.sub(r"\bI(\d+)\b", "I", text)
    text = strip_identifier(text, identifier)
    text = remove_references(text)
    text = remove_actions(text)
    text = remove_note_references(text)
    text = " ".join(text.split())

    return text.strip()

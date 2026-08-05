
import re

from parsing.text_cleaning import clean

ACTION_PATTERN = re.compile(
    r"\(\s*i\s*\)"
    r"|\bI\b"
    r"|\b[CRA]\d*\b"
)

NOTE_PATTERN = re.compile(r"(?<![,-])\b\d{1,3}\b(?![,-])")

REFERENCE_PATTERN = re.compile(
    r"See\s+DAM\s+([\d.,\sand]+)",
    re.IGNORECASE
)

RANGE_REFERENCE_PATTERN = re.compile(
    r"Refer\s+to\s+Activit(?:y|ies)\s+"
    r"(\d+(?:\.\d+)+)"
    r"(?:\s*[-–]\s*(\d+(?:\.\d+)+))?"
    r"\s+in\s+Section\s+\d+\.?",
    re.IGNORECASE
)

SEE_ID_COLON_PATTERN = re.compile(
    r"\bSee\s+(\d+(?:\.\d+)+)\s*:",
    re.IGNORECASE
)

SEE_ID_SLASH_PATTERN = re.compile(
    r"\(\s*See\s+(\d+(?:\.\d+)+)\s*/\s*(\d+(?:\.\d+)+)\s*\)",
    re.IGNORECASE
)

REFERENCE_ID_PATTERN = re.compile(r"\d+(?:\.\d+)+")


def _expand_id_range(start_id, end_id):
    """2.114, 2.117 -> ['2.114', '2.115', '2.116', '2.117']"""

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
    "I", "I1", "I2", "I3",
    "C", "C1", "C2", "C3", "C4",
    "R", "R1", "R2",
    "A", "A1", "A2", "A3",
    "( i )"
}


def strip_identifier(text, identifier):
    if identifier and text.startswith(identifier):
        return text[len(identifier):]

    return re.sub(r"^\d+(?:\.\d+)+", "", text)


def extract_references(text):
    """
    'Signature ... for See DAM 16.100, 16.200, 16.300, and 16.400
    technical cooperation' -> ['16.100', '16.200', '16.300', '16.400']

    'Communication to Government Refer to Activities 2.114 - 2.117 in
    Section 2.' -> ['2.114', '2.115', '2.116', '2.117']

    'CSP / RISP Dialogue Mission (during CSP / See 2.120: Organization
    of mission RISP preparation)' -> ['2.120'] (the "See <id>:" form -
    a redirect to a whole process rather than a specific activity)

    'Interim CSP/RISP... (See 1.114.1 / 1.114.2)' -> ['1.114.1',
    '1.114.2'] (the parenthetical "See <id> / <id>" form, pointing to
    two alternative activities rather than a range)
    """

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


def remove_references(text):
    """The one place reference phrases get stripped - 'See DAM ...',
    'Refer to Activities ... in Section ...', 'See <id>:', and
    '(See <id> / <id>)'. Everything downstream (title, note-hunting)
    calls this first, so a reference phrase can never be mistaken for
    footnote-number noise - the exact corruption these last two
    patterns were added to fix (their ids were being silently eaten,
    digit by digit, by the footnote-digit stripper instead)."""

    if not text:
        return ""

    text = REFERENCE_PATTERN.sub("", text)
    text = RANGE_REFERENCE_PATTERN.sub("", text)
    text = SEE_ID_SLASH_PATTERN.sub("", text)
    text = SEE_ID_COLON_PATTERN.sub("", text)

    return text


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


def remove_actions(text):
    if not text:
        return ""

    return ACTION_PATTERN.sub("", text)


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


def remove_note_references(text):
    if not text:
        return ""

    return NOTE_PATTERN.sub("", text)


WORD_BOUNDARY_CORRUPTION_PATTERN = re.compile(r"[a-z][A-Z]")


def looks_word_boundary_corrupted(text):
    return bool(text) and bool(WORD_BOUNDARY_CORRUPTION_PATTERN.search(text))


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

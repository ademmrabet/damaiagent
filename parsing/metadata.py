# Pulls title / actions / footnote references / cross-references out
# of a task's raw merged text.
#
# v1 had a real bug here, found by testing against real pages (2.312.2):
# extract_title() and extract_note_references() each tried to strip
# "See DAM 16.100, 16.200..." cross-reference text independently, and
# only ONE of the two paths actually did it. The other (the one title
# went through) just ran NOTE_PATTERN (a bare 1-3 digit matcher) over
# the raw text, which doesn't know "16.100" is a reference and instead
# treats each digit group in it as footnote noise and deletes them -
# producing titles like "See DAM ., ., ., and . technical cooperation".
#
# Fix: reference-stripping happens in exactly ONE place
# (`remove_references`), and every other function that needs
# reference-free text calls it first. One source of truth instead of
# two paths that can silently disagree - same lesson as the
# authority_rules.py / authority_codes.json duplication in v1.

import re

from parsing.text_cleaning import clean

ACTION_PATTERN = re.compile(
    r"\(\s*i\s*\)"
    r"|\bI\b"
    r"|\b[CRA]\d*\b"
)

# v2 bug, found via the threshold_variant test on 2.513.3.a ("Up to
# UA 2,000,000"): a bare \b\d{1,3}\b footnote-number matcher also
# matches the digit groups inside a comma-formatted amount - "2" and
# each "000" in "2,000,000" - and strips them, corrupting the title
# into "Up to UA ,,". Real footnote-reference digits in this DAM are
# always comma-free (surrounded by spaces or attached to an action
# letter, e.g. "5 I6" or "2 2"), so excluding any digit group directly
# touching a comma is a safe, evidence-based fix - not a guess.
NOTE_PATTERN = re.compile(r"(?<!,)\b\d{1,3}\b(?!,)")

REFERENCE_PATTERN = re.compile(
    r"See\s+DAM\s+([\d.,\sand]+)",
    re.IGNORECASE
)

# Second reference style, found in chapter 3 (task 3.225): a task
# whose entire row is a redirect, e.g. "Refer to Activities 2.114 -
# 2.117 in Section 2." - a RANGE, not a comma list, and it needs
# expanding (2.114..2.117), not just capturing the two endpoints.
RANGE_REFERENCE_PATTERN = re.compile(
    r"Refer\s+to\s+Activit(?:y|ies)\s+"
    r"(\d+(?:\.\d+)+)"
    r"(?:\s*[-–]\s*(\d+(?:\.\d+)+))?"
    r"\s+in\s+Section\s+\d+\.?",
    re.IGNORECASE
)

REFERENCE_ID_PATTERN = re.compile(r"\d+(?:\.\d+)+")


def _expand_id_range(start_id, end_id):
    """2.114, 2.117 -> ['2.114', '2.115', '2.116', '2.117']"""

    start_parts = start_id.split(".")
    end_parts = end_id.split(".")

    if start_parts[:-1] != end_parts[:-1]:
        # Different prefixes (e.g. different chapter) - can't safely
        # assume a numeric range makes sense, just keep both ends.
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

    return references


def remove_references(text):
    """The one place reference phrases get stripped - both 'See DAM
    ...' and 'Refer to Activities ... in Section ...'. Everything
    downstream (title, note-hunting) calls this first, so a reference
    phrase can never be mistaken for footnote-number noise."""

    if not text:
        return ""

    text = REFERENCE_PATTERN.sub("", text)
    text = RANGE_REFERENCE_PATTERN.sub("", text)

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
            # OCR fused an action letter to a stray footnote digit
            # (e.g. "C4" meant to be "C" + footnote "4") - keep the
            # letter, the digit gets picked up separately as a note.
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
    text = remove_references(text)  # <- fixed: was missing on the title path, present here

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


def extract_title(text, identifier=None):
    if not text:
        return ""

    text = clean(text)
    text = re.sub(r"\bI(\d+)\b", "I", text)
    text = strip_identifier(text, identifier)
    text = remove_references(text)     # <- fixed: this line didn't exist in v1's title path
    text = remove_actions(text)
    text = remove_note_references(text)
    text = " ".join(text.split())

    return text.strip()

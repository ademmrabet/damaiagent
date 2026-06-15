import re
from parsing.task_cleaner import (
    normalize_split_numbers,
    collapse_spaced_words,
    normalize_whitespace,
    fix_known_ocr_errors
)

ACTION_PATTERN = re.compile(
    r"\(\s*i\s*\)"
    r"|\bI\b"
    r"|\b[CRA]\d*\b"
)

NOTE_PATTERN = re.compile(
    r"\b\d{1,3}\b"
)


def extract_actions(text):
    """
    Returns:
        ['I', 'A', '( i )', 'R1']
    """

    if not text:
        return []
    text = normalize_split_numbers(text)
    text = collapse_spaced_words(text)
    text = normalize_whitespace(text)
    text = fix_known_ocr_errors(text)
    text = re.sub(
        r"\bI(\d+)\b",
        "I",
        text
    )
    return ACTION_PATTERN.findall(text)


def remove_actions(text):
    """
    Removes actions from text.
    """

    if not text:
        return ""

    return ACTION_PATTERN.sub(
        "",
        text
    )


def extract_note_references(text, identifier=None):

    if not text:
        return []
    text = normalize_split_numbers(text)
    text = collapse_spaced_words(text)
    text = normalize_whitespace(text)
    text = fix_known_ocr_errors(text)
    # remove identifier first
    clean_text = re.sub(
        r"^\d+(?:\.\d+)+",
        "",
        text
    )

    text = re.sub(
    r"^\d+(?:\.\d+)+",
    "",
    text
    )

    text = remove_actions(text)
    text = re.sub(
        r"See\s+DAM\s+[\d\.,\sand]+",
        "",
        text,
        flags=re.IGNORECASE
    )
    notes = NOTE_PATTERN.findall(text)

    unique_notes = []

    for n in notes:
        if n not in unique_notes:
            unique_notes.append(n)

    return unique_notes


def remove_note_references(text, identifier=None):

    if not text:
        return ""

    clean_text = re.sub(
        r"^\d+(?:\.\d+)+",
        "",
        text
    )

    return NOTE_PATTERN.sub(
        "",
        clean_text
    )

def extract_title(text, identifier=None):

    if not text:
        return ""
    text = normalize_split_numbers(text)
    text = collapse_spaced_words(text)
    text = normalize_whitespace(text)
    text = fix_known_ocr_errors(text)
    text = re.sub(
        r"\bI(\d+)\b",
        "I",
        text
    )
    # remove identifier
    text = re.sub(
        r"^\d+(?:\.\d+)+",
        "",
        text
    )

    # remove actions
    text = remove_actions(text)

    # remove notes
    text = remove_note_references(text)

    # normalize whitespace
    text = " ".join(
        text.split()
    )

    return text.strip()
# Splits each action code into (letter, level, footnote_refs) using
# character geometry, not text patterns - see docs/decisions.md for
# the validated rule and the real coordinates it's based on.
#
# Rule (confirmed against real coordinates - 2.224.4's "A1" + footnote
# 21, and 2.223.2/2.223.3's "C13"/"C14"):
#   - the action letter is a "big" character (size >= BODY_SIZE_MIN)
#   - a small (size < BODY_SIZE_MIN) character whose BOTTOM lines up
#     with the letter's bottom is the level digit (at most one)
#   - small characters whose TOP lines up with the letter's top are
#     footnote digits; consecutive same-height ones concatenate into
#     one multi-digit footnote number
#
# Anchor design, revised twice against real false positives on
# 2.223.2 (title: "Project Appraisal Report (PAR) for a non-
# exceptional operation"):
#   1st attempt: scan raw characters for big I/C/R/A. False-positived
#   on "A"/"R" from OCR-spaced title letters ("A p p r a is a l").
#   2nd attempt: exclude runs of single-letter WORDS. Still false-
#   positived on "A"/"R" living INSIDE an ordinary word, "(PAR)".
#   Final: only trust a WORD whose entire text already matches
#   ^[ICRA]\d*$ (i.e. it looks exactly like a bare action code with
#   nothing else attached) as an anchor. "PAR)" and "Appraisal" fail
#   that test outright - there's no partial-match risk left, because
#   the whole word has to be just the letter (+ maybe fused digits).

import re

from parsing.metadata import extract_actions

BODY_SIZE_MIN = 8.0
ALIGNMENT_TOLERANCE = 1.5  # points
MAX_DECORATION_GAP = 8.0   # points - how close a small char must be to
                           # still count as "attached" to the letter
                           # before it, rather than the start of
                           # something else entirely

LETTER_ACTION_PATTERN = re.compile(r"^[ICRA]\d*$")

# Third false-positive found on the SAME title (2.223.2): OCR-spacing
# ("A p p r a is a l", "R e p o r t") sometimes isolates the first
# letter of a word as its own one-character WORD, and a bare "A" or
# "R" with zero digits still matches LETTER_ACTION_PATTERN trivially.
# The word-match-only fix doesn't catch this - needs the spaced-run
# check back too, now applied at the word level, not mixed with
# fragile word-vs-char coordinate comparisons like the first attempt.
SPACED_WORD_GAP_MAX = 6.0  # points


def _row_chars(chars, top, bottom, pad=1.0):
    return sorted(
        (c for c in chars if top - pad <= c["top"] <= bottom + pad),
        key=lambda c: c["x0"]
    )


def _row_words(words, top, bottom, pad=1.0):
    return sorted(
        (w for w in words if top - pad <= w["top"] <= bottom + pad),
        key=lambda w: w["x0"]
    )


def _is_spaced_prose(index, row_words):
    """
    True if the word at `index` sits directly adjacent (small gap) to
    another single-letter word - i.e. it's OCR-spaced prose like
    "A p p r a is a l", not a real standalone action code. A genuine
    action code word is followed by a real gap (the next table
    column) or by nothing.
    """

    word = row_words[index]

    def _adjacent_single_letter(other):
        return (
            other is not None
            and len(other["text"]) == 1
            and other["text"].isalpha()
        )

    prev_word = row_words[index - 1] if index > 0 else None
    next_word = row_words[index + 1] if index + 1 < len(row_words) else None

    prev_close = (
        prev_word is not None
        and word["x0"] - prev_word["x1"] <= SPACED_WORD_GAP_MAX
    )
    next_close = (
        next_word is not None
        and next_word["x0"] - word["x1"] <= SPACED_WORD_GAP_MAX
    )

    return (
        (prev_close and _adjacent_single_letter(prev_word))
        or (next_close and _adjacent_single_letter(next_word))
    )


def _anchor_chars_from_words(row_words, row_chars):
    """
    The big letter character belonging to each WORD whose entire text
    matches ^[ICRA]\\d*$ - e.g. "A", "C13", "R1" - and that isn't
    itself sitting inside a run of OCR-spaced single letters. A word
    like "PAR)" never matches the pattern at all; a lone spaced "A"
    from "Appraisal" matches the pattern but gets caught by the
    adjacency check instead.
    """

    anchors = []

    for i, w in enumerate(row_words):

        if not LETTER_ACTION_PATTERN.fullmatch(w["text"]):
            continue

        if _is_spaced_prose(i, row_words):
            continue

        candidates = [
            c for c in row_chars
            if abs(c["x0"] - w["x0"]) < 0.5 and c["size"] >= BODY_SIZE_MIN
        ]

        if candidates:
            anchors.append(candidates[0])

    return anchors


def _decoration_chars(anchor, following_chars, territory_end_x0):
    """
    Small characters immediately after `anchor`, up to whichever comes
    first: a gap too large to still be "attached", a character that
    isn't small (size < BODY_SIZE_MIN), or the start of the next
    action's territory.
    """

    decorations = []
    cursor_x1 = anchor["x1"]

    for c in following_chars:

        if c["x0"] >= territory_end_x0:
            break

        if c["size"] >= BODY_SIZE_MIN:
            break

        if c["x0"] - cursor_x1 > MAX_DECORATION_GAP:
            break

        decorations.append(c)
        cursor_x1 = c["x1"]

    return decorations


def _split_level_and_footnotes(anchor, decorations):

    level = None
    footnote_digits = []

    for c in decorations:

        bottom_aligned = abs(c["bottom"] - anchor["bottom"]) <= ALIGNMENT_TOLERANCE
        top_aligned = abs(c["top"] - anchor["top"]) <= ALIGNMENT_TOLERANCE

        if bottom_aligned and not top_aligned and level is None and c["text"].isdigit():
            level = int(c["text"])
            continue

        if top_aligned and c["text"].isdigit():
            footnote_digits.append(c)
            continue

        # Doesn't cleanly match either alignment - not confident
        # enough to guess, so it's left out rather than risk a wrong
        # answer. Worth a look if validation flags a lot of these.

    footnotes = []

    if footnote_digits:

        footnote_digits.sort(key=lambda c: c["x0"])
        current_number = footnote_digits[0]["text"]
        prev = footnote_digits[0]

        for c in footnote_digits[1:]:

            same_height = (
                abs(c["top"] - prev["top"]) <= ALIGNMENT_TOLERANCE
                and abs(c["bottom"] - prev["bottom"]) <= ALIGNMENT_TOLERANCE
            )
            adjacent = c["x0"] - prev["x1"] <= MAX_DECORATION_GAP

            if same_height and adjacent:
                current_number += c["text"]
            else:
                footnotes.append(int(current_number))
                current_number = c["text"]

            prev = c

        footnotes.append(int(current_number))

    return level, footnotes


def extract_action_instances(text, chars, words, top, bottom):
    """
    `text`: the task block's raw merged text (what extract_actions()
    already works on) - used only as a sanity cross-check on count.
    `chars`: page.chars for the page this task is on.
    `words`: page.extract_words() for the page this task is on.
    `top`/`bottom`: the task block's vertical span.

    Returns a list of {"action", "level", "footnote_refs"} dicts, one
    per action code found - action is the bare letter+level combined
    ("C", "A1"), matching parsing.metadata.VALID_ACTIONS shape. Role
    (which column/person) is NOT resolved here - separate work item
    (column x-position -> role name mapping).
    """

    letter_actions = [
        a for a in extract_actions(text)
        if LETTER_ACTION_PATTERN.fullmatch(a)
    ]

    if not letter_actions:
        return []

    band_chars = _row_chars(chars, top, bottom)
    band_words = _row_words(words, top, bottom)

    anchors = _anchor_chars_from_words(band_words, band_chars)
    anchors.sort(key=lambda c: c["x0"])

    instances = []

    for i, anchor in enumerate(anchors):

        next_anchor_x0 = (
            anchors[i + 1]["x0"] if i + 1 < len(anchors) else anchor["x0"] + 40
        )

        following = [c for c in band_chars if c["x0"] > anchor["x0"]]
        decorations = _decoration_chars(anchor, following, next_anchor_x0)
        level, footnotes = _split_level_and_footnotes(anchor, decorations)

        action = f"{anchor['text']}{level}" if level is not None else anchor["text"]

        instances.append({
            "action": action,
            "level": level,
            "footnote_refs": footnotes
        })

    return instances

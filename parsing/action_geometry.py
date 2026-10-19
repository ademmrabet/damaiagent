import re

from parsing.metadata import extract_actions

BODY_SIZE_MIN = 8.0

ALIGNMENT_TOLERANCE = 2.0
MAX_DECORATION_GAP = 8.0

LETTER_ACTION_PATTERN = re.compile(r"^[ICRA]\d*$")

SPACED_WORD_GAP_MAX = 6.0


# characters that sit on the same row, sorted left to right
def _row_chars(chars, top, bottom, pad=1.0):
    return sorted(
        (c for c in chars if top - pad <= c["top"] <= bottom + pad),
        key=lambda c: c["x0"],
    )


# words that sit on the same row, sorted left to right
def _row_words(words, top, bottom, pad=1.0):
    return sorted(
        (w for w in words if top - pad <= w["top"] <= bottom + pad),
        key=lambda w: w["x0"],
    )


# true if a single letter sits next to other single letters (spaced text)
def _is_spaced_prose(index, row_words):

    word = row_words[index]

    def _adjacent_single_letter(other):
        return other is not None and len(other["text"]) == 1 and other["text"].isalpha()

    prev_word = row_words[index - 1] if index > 0 else None
    next_word = row_words[index + 1] if index + 1 < len(row_words) else None

    prev_close = (
        prev_word is not None and word["x0"] - prev_word["x1"] <= SPACED_WORD_GAP_MAX
    )
    next_close = (
        next_word is not None and next_word["x0"] - word["x1"] <= SPACED_WORD_GAP_MAX
    )

    return (prev_close and _adjacent_single_letter(prev_word)) or (
        next_close and _adjacent_single_letter(next_word)
    )


# the big action letters (A, C, R, I) found as standalone words
def _anchor_chars_from_words(row_words, row_chars):

    anchors = []

    for i, w in enumerate(row_words):

        if not LETTER_ACTION_PATTERN.fullmatch(w["text"]):
            continue

        if _is_spaced_prose(i, row_words):
            continue

        candidates = [
            c
            for c in row_chars
            if abs(c["x0"] - w["x0"]) < 0.5 and c["size"] >= BODY_SIZE_MIN
        ]

        if candidates:
            anchors.append(candidates[0])

    return anchors


# small level and footnote digits right after an action letter
def _decoration_chars(anchor, following_chars, territory_end_x0):

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


# separate the level digit from footnote digits using their font size
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


# find the informed markers (i) and the column they sit in
def extract_informed_instances(chars, top, bottom):

    band = [c for c in _row_chars(chars, top, bottom) if c["text"].strip() != ""]
    instances = []

    i = 0
    while i < len(band) - 2:

        a, b, c = band[i], band[i + 1], band[i + 2]

        if (
            a["text"] == "("
            and b["text"].strip().lower() == "i"
            and c["text"] == ")"
            and (b["x0"] - a["x1"]) <= MAX_DECORATION_GAP
            and (c["x0"] - b["x1"]) <= MAX_DECORATION_GAP
        ):
            instances.append(
                {"action": "( i )", "level": None, "footnote_refs": [], "x0": a["x0"]}
            )
            i += 3
            continue

        i += 1

    return instances


# find every action letter with its level, footnotes and column
def extract_action_instances(text, chars, words, top, bottom):

    letter_actions = [
        a for a in extract_actions(text) if LETTER_ACTION_PATTERN.fullmatch(a)
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

        instances.append(
            {
                "action": action,
                "level": level,
                "footnote_refs": footnotes,
                "x0": anchor["x0"],
            }
        )

    return instances

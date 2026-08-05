
import re
from collections import defaultdict

from parsing.metadata import ACTION_PATTERN

ROW_MERGE_MAX_GAP = 5.0


def _is_pure_action_row(row_words):
    """
    True if a row's words are ENTIRELY action codes / informed markers
    with nothing else left over. A real table row can't be made of
    just action codes with no identifier, title, or prose - so this is
    a narrow, safe signal that a row-bucket is a stray fragment of
    some other row, not a genuine standalone line.

    Real bug found testing this against 3.112/3.113 (page index 58):
    ACTION_PATTERN's "I" branch is `\\bI\\b`, which can't match inside
    "I2" - there's no word boundary between a letter and the digit
    immediately following it, so "I2"/"I3"/"I4" survived
    ACTION_PATTERN.sub() untouched and left residue, making a
    genuinely pure-action row ("I2 I3 I4 A5 A6") look impure and
    silently skip the merge. metadata.extract_actions() already
    normalizes this (`\\bI(\\d+)\\b` -> "I") before matching - applying
    the same normalization here instead of inventing a second, subtly
    different check for the same thing.
    """

    text = " ".join(w["text"] for w in row_words).strip()
    text = re.sub(r"\bI(\d+)\b", "I", text)
    return bool(text) and not ACTION_PATTERN.sub("", text).strip()


def _x_overlap(row_a, row_b):
    for wa in row_a:
        for wb in row_b:
            if wa["x0"] < wb["x1"] and wb["x0"] < wa["x1"]:
                return True
    return False


def _merge_split_action_rows(rows):
    """
    For every row-bucket that is pure action-code content, checks its
    immediate neighbors (previous and next by y - not assumed to
    always be "the next row"; the real cases found so far all merge
    forward, but nothing guarantees a future case couldn't be the
    reverse) and merges it into whichever one is close enough
    (<= ROW_MERGE_MAX_GAP) AND has zero overlapping word x-ranges -
    the geometric signature of "this is a missing piece of that row",
    confirmed against the real 3.111/3.112/3.113 case before writing
    this.
    """

    ys = sorted(rows.keys())
    merged_away = set()

    for i, y in enumerate(ys):

        if y in merged_away or not _is_pure_action_row(rows[y]):
            continue

        neighbor_ys = [ys[i - 1]] if i > 0 else []
        if i + 1 < len(ys):
            neighbor_ys.append(ys[i + 1])

        for neighbor_y in neighbor_ys:

            if neighbor_y in merged_away:
                continue

            if abs(neighbor_y - y) > ROW_MERGE_MAX_GAP:
                continue

            if _x_overlap(rows[y], rows[neighbor_y]):
                continue

            rows[neighbor_y] = sorted(
                rows[neighbor_y] + rows[y], key=lambda w: w["x0"]
            )
            merged_away.add(y)
            break

    for y in merged_away:
        del rows[y]

    return rows


def build_rows(words):
    """
    Returns {rounded_top_y: [word_dicts_sorted_by_x0]}.
    Rounding the y-coordinate absorbs the small sub-pixel jitter
    between words that are visually on the same line but not
    reported at the exact same "top" value. _merge_split_action_rows
    then catches the wider-row case rounding alone can't - see module
    docstring.
    """

    rows = defaultdict(list)

    for w in words:
        key = round(w["top"])
        rows[key].append(w)

    for row in rows.values():
        row.sort(key=lambda w: w["x0"])

    return _merge_split_action_rows(rows)


def build_char_rows(chars):
    """
    Character-level equivalent of build_rows() - groups raw
    characters into rows by y-position instead of pdfplumber's own
    pre-computed words.

    Why this exists: real bug found via agent output on task 2.223.2's
    title ("Project Appraisal Report (PAR) for a non-exceptional
    operation"). This page has two lines of body text sitting close
    together (a normal wrapped title, "...for a non-" / "exceptional
    operation11"), and pdfplumber's OWN extract_words() - before any
    of this project's code even runs - merges characters from BOTH
    lines into garbled single "words" ('ro', 'je', 'c', 't' instead of
    'Project'). It's not a row-clustering bug on this project's side;
    the word list handed in is already corrupted. Checked directly:
    grouping the raw CHARACTERS by rounded top (exactly like
    build_rows() already does for words) correctly separates the two
    lines, because each line's characters are recovered from their
    real positions rather than pdfplumber's word-boundary guess.

    Deliberately NOT run through _merge_split_action_rows() - this is
    only used to re-derive clean text for an already-known span (see
    char_lines() / callers in modeling/build_nodes.py), not to drive
    task_blocks.py's own row-by-row walk.
    """

    rows = defaultdict(list)

    for c in chars:
        key = round(c["top"])
        rows[key].append(c)

    for row in rows.values():
        row.sort(key=lambda c: c["x0"])

    return rows


def char_lines(rows):
    """
    Character-level equivalent of ordered_lines() - concatenates each
    row's characters DIRECTLY (no inserted separator), since real
    space characters are already present in the character stream.
    ordered_lines() inserts a space between each WORD because that's
    correct for words; doing the same for individual characters would
    put a space between every single letter.
    """

    lines = []

    for y in sorted(rows.keys()):

        row_chars = rows[y]
        text = "".join(c["text"] for c in row_chars)

        lines.append({
            "text": text,
            "top": min(c["top"] for c in row_chars),
            "bottom": max(c["bottom"] for c in row_chars)
        })

    return lines


def ordered_lines(rows):
    """
    Flattens the {y: [words]} map into a top-to-bottom list of
    {"text", "top", "bottom"} dicts - the shape task_blocks.py
    actually walks through.

    Real bug found testing the row-split merge fix: this used to
    report both "top" and "bottom" as the bucket's key y - fine when
    every word in a row-bucket was within ~1pt of that key anyway, but
    _merge_split_action_rows() can now combine words up to
    ROW_MERGE_MAX_GAP (5pt) apart into one bucket. A single point
    value plus action_geometry.py's +/-1pt search pad was too narrow
    to still reach the far side of a merged row - 3.111's real,
    correctly-merged "A3"/"A4" text was invisible to the geometry
    extractor because its true character y-range fell just outside
    the search band. Reporting the row's ACTUAL min/max span (not a
    single repeated point) fixes this at the source, for both merged
    and ordinary single-line rows alike.
    """

    lines = []

    for y in sorted(rows.keys()):

        row_words = rows[y]
        text = " ".join(w["text"] for w in row_words).strip()

        lines.append({
            "text": text,
            "top": min(w["top"] for w in row_words),
            "bottom": max(w["bottom"] for w in row_words)
        })

    return lines

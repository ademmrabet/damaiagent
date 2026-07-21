# Groups words into physical text rows by y-position, then sorts each
# row left-to-right by x-position. This is the row-clustering that
# solves pdfplumber handing back individual words with no line
# structure. Not implicated in any bug found in v1 - ported unchanged.

from collections import defaultdict


def build_rows(words):
    """
    Returns {rounded_top_y: [word_dicts_sorted_by_x0]}.
    Rounding the y-coordinate absorbs the small sub-pixel jitter
    between words that are visually on the same line but not
    reported at the exact same "top" value.
    """

    rows = defaultdict(list)

    for w in words:
        key = round(w["top"])
        rows[key].append(w)

    for row in rows.values():
        row.sort(key=lambda w: w["x0"])

    return rows


def ordered_lines(rows):
    """
    Flattens the {y: [words]} map into a top-to-bottom list of
    {"text", "top", "bottom"} dicts - the shape task_blocks.py
    actually walks through.
    """

    lines = []

    for y in sorted(rows.keys()):

        text = " ".join(w["text"] for w in rows[y]).strip()

        lines.append({
            "text": text,
            "top": y,
            "bottom": y
        })

    return lines

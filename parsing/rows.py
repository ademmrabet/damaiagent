import re
from collections import defaultdict

from parsing.metadata import ACTION_PATTERN

ROW_MERGE_MAX_GAP = 5.0


# true if a row holds only action codes
def _is_pure_action_row(row_words):

    text = " ".join(w["text"] for w in row_words).strip()
    text = re.sub(r"\bI(\d+)\b", "I", text)
    return bool(text) and not ACTION_PATTERN.sub("", text).strip()


# true if two rows have words at the same horizontal position
def _x_overlap(row_a, row_b):
    for wa in row_a:
        for wb in row_b:
            if wa["x0"] < wb["x1"] and wb["x0"] < wa["x1"]:
                return True
    return False


# glue action-only rows back to the task row they belong to
def _merge_split_action_rows(rows):

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

            rows[neighbor_y] = sorted(rows[neighbor_y] + rows[y], key=lambda w: w["x0"])
            merged_away.add(y)
            break

    for y in merged_away:
        del rows[y]

    return rows


# group words into rows by their vertical position
def build_rows(words):

    rows = defaultdict(list)

    for w in words:
        key = round(w["top"])
        rows[key].append(w)

    for row in rows.values():
        row.sort(key=lambda w: w["x0"])

    return _merge_split_action_rows(rows)


# same as build_rows but from characters
def build_char_rows(chars):

    rows = defaultdict(list)

    for c in chars:
        key = round(c["top"])
        rows[key].append(c)

    for row in rows.values():
        row.sort(key=lambda c: c["x0"])

    return rows


# rebuild each row's text straight from its characters
def char_lines(rows):

    lines = []

    for y in sorted(rows.keys()):

        row_chars = rows[y]
        text = "".join(c["text"] for c in row_chars)

        lines.append(
            {
                "text": text,
                "top": min(c["top"] for c in row_chars),
                "bottom": max(c["bottom"] for c in row_chars),
            }
        )

    return lines


# rows as text lines from top to bottom
def ordered_lines(rows):

    lines = []

    for y in sorted(rows.keys()):

        row_words = rows[y]
        text = " ".join(w["text"] for w in row_words).strip()

        lines.append(
            {
                "text": text,
                "top": min(w["top"] for w in row_words),
                "bottom": max(w["bottom"] for w in row_words),
            }
        )

    return lines

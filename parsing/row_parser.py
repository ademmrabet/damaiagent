from collections import defaultdict
import re

task_pattern = re.compile(r"^\d+\.\d+\.\d+")
section_pattern = re.compile(r"^\d+\.\d+\s")


def build_rows(words):
    rows = defaultdict(list)

    for w in words:
        key = round(w["top"])
        rows[key].append(w)

    for row in rows.values():
        row.sort(key=lambda w: w["x0"])

    return rows

def classify_rows(rows):
    filtered_rows = []

    for y in sorted(rows.keys()):
        line = " ". join(w["text"] for w in rows[y])

        if task_pattern.match(line):
            filtered_rows.append({
                "type": "task",
                "line": line,
                "top": y,
            })
        elif section_pattern.match(line):
            filtered_rows.append({
                "type": "section",
                "line": line,
                "top": y,
            })

    return filtered_rows
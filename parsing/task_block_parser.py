import re

TASK_PATTERN = re.compile(
    r"^\d+\.\d+\.\d+|^\d+\.\d{3}\b"
)
SECTION_PATTERN = re.compile(
    r"^\d+\.\d+\s+[A-Z]"
)
NOTES_PATTERN = re.compile(r"^Notes\s+on", re.IGNORECASE)


def build_task_blocks(rows):

    ordered_rows = []

    for y in sorted(rows.keys()):

        line = " ".join(
            w["text"]
            for w in rows[y]
        )

        ordered_rows.append(line)

    blocks = []
    current_task = None

    for line in ordered_rows:

        if TASK_PATTERN.match(line):

            if current_task:
                blocks.append(current_task)

            current_task = line
            continue

        if SECTION_PATTERN.match(line):

            if current_task:
                blocks.append(current_task)
                current_task = None

            continue

        if NOTES_PATTERN.match(line):

            if current_task:
                blocks.append(current_task)
                current_task = None

            continue

        if current_task:
            current_task += " " + line

    if current_task:
        blocks.append(current_task)

    return blocks
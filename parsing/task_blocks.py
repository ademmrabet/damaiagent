
import re

from parsing.metadata import ACTION_PATTERN, NOTE_PATTERN

SECTION_PATTERN = re.compile(r"^\d+\.\d\s+[A-Z]")

NOTES_PATTERN = re.compile(r"^Notes\s+(on|to)\b", re.IGNORECASE)
IDENTIFIER_PATTERN = re.compile(r"^\d+(?:\.\d+)+$")

LETTER_LABEL_PATTERN = re.compile(r"^\(([a-h]|[j-z])\)$")


def build_task_blocks(lines):
    """
    `lines`: output of parsing.rows.ordered_lines() - a top-to-bottom
    list of {"text", "top", "bottom"}.

    Returns a list of {"text", "top", "bottom"} blocks, one per
    task/child_task. Process/chapter boundary rows and footnote
    sections are consumed to close the current block, not emitted as
    blocks themselves - build_hierarchy_skeleton (next stage) is what
    captures process/chapter identifiers.
    """

    blocks = []
    current_task = None
    pending_title = None
    last_child_task_id = None

    def open_task(line, row):
        nonlocal pending_title

        text = line
        if pending_title:
            text = line + " " + pending_title
            pending_title = None

        return {"text": text, "top": row["top"], "bottom": row["bottom"]}

    def close_task():
        nonlocal current_task
        if current_task:
            blocks.append(current_task)
            current_task = None

    def attach(line, row):
        current_task["text"] += " " + line
        current_task["bottom"] = row["bottom"]

    for i, row in enumerate(lines):

        line = row["text"]

        if not line:
            if current_task:
                current_task["bottom"] = row["bottom"]
            continue

        if NOTES_PATTERN.match(line):
            close_task()
            pending_title = None
            continue

        if SECTION_PATTERN.match(line):
            close_task()
            pending_title = None
            continue

        tokens = line.split()
        identifier = tokens[0]

        if LETTER_LABEL_PATTERN.fullmatch(identifier) and last_child_task_id:

            close_task()

            letter = identifier[1]
            rest = line[len(identifier):].strip()
            constructed_id = f"{last_child_task_id}.{letter}"

            current_task = {
                "text": f"{constructed_id} {rest}".rstrip(),
                "top": row["top"],
                "bottom": row["bottom"]
            }
            continue

        if not IDENTIFIER_PATTERN.fullmatch(identifier):

            task_ends_with_period = (
                current_task is not None
                and current_task["text"].rstrip().endswith(".")
            )

            first_action = ACTION_PATTERN.search(line)

            line_leads_with_prose_then_actions = (
                first_action is not None
                and line[:first_action.start()].strip() != ""
            )

            current_already_has_actions = (
                current_task is not None
                and bool(ACTION_PATTERN.search(current_task["text"]))
            )

            task_looks_finished = (
                task_ends_with_period
                or (line_leads_with_prose_then_actions and current_already_has_actions)
            )

            if current_task and not task_looks_finished:
                attach(line, row)
                continue

            next_row = lines[i + 1] if i + 1 < len(lines) else None
            next_line = next_row["text"].strip() if next_row else ""
            next_tokens = next_line.split()

            next_is_title_split = False

            if next_tokens and IDENTIFIER_PATTERN.fullmatch(next_tokens[0]):
                remainder = next_line[len(next_tokens[0]):]
                remainder = ACTION_PATTERN.sub("", remainder)
                remainder = NOTE_PATTERN.sub("", remainder)

                if not remainder.strip():
                    next_is_title_split = True

            if next_is_title_split:
                close_task()
                pending_title = line
                continue

            if current_task:
                attach(line, row)


            continue

        parts = identifier.split(".")

        if len(parts) == 3:
            close_task()
            current_task = open_task(line, row)
            last_child_task_id = identifier
            continue

        if len(parts) == 2:

            try:
                suffix_num = int(parts[1])
            except ValueError:
                if current_task:
                    attach(line, row)
                continue

            if suffix_num % 10 == 0:
                close_task()
                pending_title = None
                continue

            close_task()
            current_task = open_task(line, row)
            continue

        if current_task:
            attach(line, row)

    close_task()

    return blocks

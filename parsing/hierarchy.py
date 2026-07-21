# Turns a DAM identifier string into hierarchy facts, purely from the
# numbering scheme - no PDF layout involved. This logic checked out
# correct against real data in the schema review (chapter "X",
# process "X.XX0", task "X.XXX", child "X.XXX.X") - ported unchanged.

import re

# Trailing (?:\.[a-z])? handles threshold_variant ids like "2.513.3.a"
# - task_blocks.py constructs these itself (the PDF only ever prints
# the bare "(a)", never the full id), so this only needs to round-trip
# what task_blocks.py already built, not parse it from raw PDF text.
ID_PATTERN = re.compile(r"^\d+(?:\.\d+)+(?:\.[a-z])?")


def get_identifier(line):
    """
    '2.221 Project Identification' -> '2.221'
    '2.221.1 E&S Categorisation Memorandum' -> '2.221.1'
    '2.513.3.a Up to UA 2,000,000' -> '2.513.3.a'
    """

    if not line:
        return None

    match = ID_PATTERN.match(line)

    return match.group() if match else None


def get_chapter(identifier):
    # 2.221.1 -> '2'
    if not identifier:
        return None

    return identifier.split(".")[0]


def get_node_type(identifier):
    """
    X         -> chapter (handled by caller before this; identifiers
                 here always have a dot, see get_identifier)
    X.YY0     -> process
    X.YYY     -> task
    X.YYY.N   -> child_task
    X.YYY.N.a -> threshold_variant (letter-labeled sub-item of a
                 child_task, e.g. 2.513.3.a - see schema.py)
    """

    if not identifier:
        return None

    parts = identifier.split(".")

    if len(parts) == 4:
        return "threshold_variant"

    if len(parts) == 3:
        return "child_task"

    if len(parts) == 2:
        middle = int(parts[1])
        return "process" if middle % 10 == 0 else "task"

    return None


def get_process_id(identifier):
    """
    2.221.1 -> 2.220
    2.221   -> 2.220
    2.110   -> 2.110
    3.683.4 -> 3.680
    """

    if not identifier:
        return None

    chapter = get_chapter(identifier)
    parts = identifier.split(".")

    if len(parts) < 2:
        return None

    middle = int(parts[1])
    process_number = (middle // 10) * 10

    return f"{chapter}.{process_number:03d}"


def get_parent_task_id(identifier):
    # 2.221.1 -> 2.221 ; 2.112 -> None (tasks have no parent_task_id,
    # only child_tasks do - their "parent" is the process, tracked
    # via process_id, not parent_task_id)
    # 2.513.3.a -> 2.513.3 (a threshold_variant's parent is the
    # child_task it's a condition of)
    if not identifier:
        return None

    parts = identifier.split(".")

    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}"

    if len(parts) != 3:
        return None

    return f"{parts[0]}.{parts[1]}"


def get_children(task_id, all_ids):

    prefix = task_id + "."

    children = [
        identifier for identifier in all_ids
        if identifier.startswith(prefix)
    ]

    return sorted(children)


def has_children(task_id, all_ids):
    return len(get_children(task_id, all_ids)) > 0

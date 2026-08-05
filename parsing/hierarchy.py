
import re

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
    if not identifier:
        return None

    parts = identifier.split(".")

    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}"

    if len(parts) != 3:
        return None

    return f"{parts[0]}.{parts[1]}"


def get_children(task_id, all_ids):
    """
    Direct children only, derived from each candidate's OWN parent
    pointer - not string-prefix guessing.

    Real bug found testing modeling/build_nodes.py against the full
    document once threshold_variant ids were in the mix: prefix
    matching ("does this id start with task_id + '.'") is only
    actually true for child_task->threshold_variant and
    task->child_task, because those ids are literally longer strings
    built from their parent's id. It's FALSE for process->task
    ("2.513" does not start with "2.510." - task ids aren't string
    extensions of their process id, they're grouped into it by
    get_process_id()'s round-down-to-10 math) and for chapter->process
    (a chapter's "children" under prefix matching becomes every
    descendant at every depth flattened together, not just its
    processes). Silently wrong in two of four cases, not caught until
    threshold_variant ids made a task's grandchildren start colliding
    with its direct children under the same prefix.

    Fix: ask each candidate id what ITS parent actually is (the same
    get_process_id/get_parent_task_id/get_chapter functions already
    used to populate the node's own fields) and keep only the ones
    that point back at task_id. Same information, just read in the
    correct direction instead of guessed from string shape.
    """


    node_type = "chapter" if "." not in task_id else get_node_type(task_id)
    children = []

    for identifier in all_ids:

        if identifier == task_id:
            continue

        candidate_type = get_node_type(identifier)

        if node_type == "chapter":
            if candidate_type == "process" and get_chapter(identifier) == task_id:
                children.append(identifier)

        elif node_type == "process":
            if candidate_type == "task" and get_process_id(identifier) == task_id:
                children.append(identifier)

        elif node_type == "task":
            if candidate_type == "child_task" and get_parent_task_id(identifier) == task_id:
                children.append(identifier)

        elif node_type == "child_task":
            if candidate_type == "threshold_variant" and get_parent_task_id(identifier) == task_id:
                children.append(identifier)


    return sorted(children)


def has_children(task_id, all_ids):
    return len(get_children(task_id, all_ids)) > 0

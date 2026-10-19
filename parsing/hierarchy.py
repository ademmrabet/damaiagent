import re

ID_PATTERN = re.compile(r"^\d+(?:\.\d+)+(?:\.[a-z])?")


# pull the leading id like 2.221.1 off a line
def get_identifier(line):

    if not line:
        return None

    match = ID_PATTERN.match(line)

    return match.group() if match else None


# chapter is the first part of the id
def get_chapter(identifier):
    if not identifier:
        return None

    return identifier.split(".")[0]


# chapter, process, task, child task or threshold variant, decided by the id shape
def get_node_type(identifier):

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


# id of the process a task belongs to, like 2.221 to 2.220
def get_process_id(identifier):

    if not identifier:
        return None

    chapter = get_chapter(identifier)
    parts = identifier.split(".")

    if len(parts) < 2:
        return None

    middle = int(parts[1])
    process_number = (middle // 10) * 10

    return f"{chapter}.{process_number:03d}"


# id of the parent, or none for top-level tasks
def get_parent_task_id(identifier):
    if not identifier:
        return None

    parts = identifier.split(".")

    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}"

    if len(parts) != 3:
        return None

    return f"{parts[0]}.{parts[1]}"


# direct children of an id
def get_children(task_id, all_ids):

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
            if (
                candidate_type == "child_task"
                and get_parent_task_id(identifier) == task_id
            ):
                children.append(identifier)

        elif node_type == "child_task":
            if (
                candidate_type == "threshold_variant"
                and get_parent_task_id(identifier) == task_id
            ):
                children.append(identifier)

    return sorted(children)


# true if any other id sits under this one
def has_children(task_id, all_ids):
    return len(get_children(task_id, all_ids)) > 0

import re


ID_PATTERN = re.compile(
    r"^\d+(?:\.\d+)+"
)


def get_identifier(line):
    """
    Examples:
        '2.221 Project Identification'
            -> '2.221'

        '2.221.1 E&S Categorisation Memorandum'
            -> '2.221.1'
    """

    if not line:
        return None

    match = ID_PATTERN.match(line)

    if match:
        return match.group()

    return None


def get_chapter(identifier):
    """
    2.221.1 -> '2'
    1.110 -> '1'
    """

    if not identifier:
        return None

    return identifier.split(".")[0]


def get_node_type(identifier):
    """
    Returns:
        process
        task
        child_task
    """

    if not identifier:
        return None

    parts = identifier.split(".")

    # X.YYY.N
    if len(parts) == 3:
        return "child_task"

    # X.YYY
    if len(parts) == 2:

        middle = int(parts[1])

        # X.YY0
        if middle % 10 == 0:
            return "process"

        # X.YYY
        return "task"

    return None


def get_process_id(identifier):
    """
    Examples:

    2.221.1 -> 2.220
    2.221 -> 2.220
    2.110 -> 2.110
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
    """
    Examples:

    2.221.1 -> 2.221
    1.111.2 -> 1.111
    2.112 -> None
    """

    if not identifier:
        return None

    parts = identifier.split(".")

    if len(parts) != 3:
        return None

    return f"{parts[0]}.{parts[1]}"

def get_children(task_id, all_ids):

    children = []

    prefix = task_id + "."

    for identifier in all_ids:

        if identifier.startswith(prefix):
            children.append(identifier)

    return sorted(children)

def has_children(task_id, all_ids):

    return len(
        get_children(
            task_id,
            all_ids
        )
    ) > 0

from extraction.table_extractor import extract_words
from parsing.rows import build_rows, ordered_lines
from parsing.hierarchy import (
    get_identifier,
    get_chapter,
    get_node_type,
    get_process_id,
    get_parent_task_id,
    get_children,
    has_children
)


def scan_all_identifiers(pdf):
    """Every distinct chapter/process/task/child_task id found on any
    page, via plain text scanning (no geometry)."""

    ids = set()

    for page in pdf.pages:

        lines = ordered_lines(build_rows(extract_words(page)))

        for line in lines:

            identifier = get_identifier(line["text"])

            if identifier:
                ids.add(identifier)

    return ids


def build_skeleton(ids):
    """
    {id: {id, chapter, node_type, process_id, parent_task_id,
    has_children, children}} for every id found - the hierarchy shape,
    nothing else yet. Chapter numbers themselves (bare "1", "2", "3")
    are never in `ids` (get_identifier requires a dot) - they get
    synthesized later from the set of chapters seen here.
    """

    all_ids = sorted(ids)
    skeleton = {}

    for identifier in all_ids:

        skeleton[identifier] = {
            "id": identifier,
            "chapter": get_chapter(identifier),
            "node_type": get_node_type(identifier),
            "process_id": get_process_id(identifier),
            "parent_task_id": get_parent_task_id(identifier),
            "has_children": has_children(identifier, all_ids),
            "children": get_children(identifier, all_ids)
        }

    return skeleton

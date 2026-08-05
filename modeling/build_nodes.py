
import re

import pdfplumber

from extraction.table_extractor import extract_words, extract_characters
from parsing.rows import build_rows, ordered_lines, build_char_rows, char_lines
from parsing.task_blocks import build_task_blocks
from parsing.hierarchy import (
    get_identifier,
    get_chapter,
    get_node_type,
    get_process_id,
    get_parent_task_id,
    get_children,
    has_children,
)
from parsing.metadata import extract_title, extract_references, looks_word_boundary_corrupted
from parsing.action_geometry import extract_action_instances, extract_informed_instances
from parsing.column_roles import extract_column_headers, nearest_role
from schema.schema import Node, Responsibility


def _process_title_from_line(line_text, identifier):
    """
    task_blocks.py deliberately discards process boundary rows (e.g.
    "2.220 LOAN / GRANT PROCESSING") without emitting a block, so their
    titles have to be read directly off the raw line here instead -
    this is the only place they're captured.
    """

    return " ".join(line_text[len(identifier):].split())


_LONG_DIGIT_RUN = re.compile(r"(?<!\d)\d{4,}(?!\d)")
_STRAY_PERIOD = re.compile(r"(?<!\w)\.(?!\w)")


def _reconstruct_clean_block_text(chars, top, bottom, pad=1.0):
    """
    Character-level fallback for a block whose word-based text looks
    corrupted (see parsing.metadata.looks_word_boundary_corrupted and
    parsing.rows.build_char_rows - real bug found via agent output:
    pdfplumber's OWN word extraction can merge two close-together
    lines' characters into garbled words before this project's code
    ever sees them). Re-derives the block's text directly from raw
    characters within its known top/bottom span instead of trusting
    the word list.

    Trade-off found testing this: character concatenation is exactly
    right for real prose (real spaces are already literal characters
    in the stream), but the ACTIONS/footnote row within the same
    block has no such spacing between adjacent footnote digits from
    different columns - they land glued together as long runs like
    "13131316" that NOTE_PATTERN (`\\b\\d{1,3}\\b`) can't split (no
    word-boundary exists INSIDE an unbroken digit run). Rather than
    reimplementing action/footnote-column separation at the character
    level - task_blocks.py and action_geometry.py already do that job
    well from words/geometry - just strip what's clearly leftover
    contamination: digit runs of 4+ (longer than any real footnote
    number in this DAM) and stray standalone periods (footnote
    numbering markers like "1." with the digit already stripped
    elsewhere). Known trade-off, not a complete character-level
    parser - documented in docs/decisions.md.
    """

    band_chars = [c for c in chars if top - pad <= c["top"] <= bottom + pad]
    lines = char_lines(build_char_rows(band_chars))

    text = " ".join(line["text"].strip() for line in lines if line["text"].strip())
    text = _LONG_DIGIT_RUN.sub("", text)
    text = _STRAY_PERIOD.sub("", text)

    return " ".join(text.split())


def build_nodes(pdf_path):
    """
    Returns {id: schema.Node}, covering every chapter, process, task,
    child_task, and threshold_variant found in the document.
    """

    pdf = pdfplumber.open(pdf_path)

    enriched = {}
    process_titles = {}
    all_task_child_ids = set()
    last_headers = []

    for page_index, page in enumerate(pdf.pages):

        words = extract_words(page)
        chars = extract_characters(page)
        lines = ordered_lines(build_rows(words))

        for line in lines:
            identifier = get_identifier(line["text"])
            if identifier and get_node_type(identifier) == "process":
                process_titles[identifier] = _process_title_from_line(line["text"], identifier)

        headers = extract_column_headers(chars)
        if headers:
            last_headers = headers
        page_headers = last_headers

        blocks = build_task_blocks(lines)

        for block in blocks:

            identifier = get_identifier(block["text"])
            if not identifier:
                continue

            all_task_child_ids.add(identifier)

            title = extract_title(block["text"], identifier)
            references = extract_references(block["text"])

            if looks_word_boundary_corrupted(title):
                clean_text = _reconstruct_clean_block_text(
                    chars, block["top"], block["bottom"]
                )
                clean_title = extract_title(clean_text, identifier)
                if not looks_word_boundary_corrupted(clean_title):
                    title = clean_title
                    references = extract_references(clean_text)

            action_instances = extract_action_instances(
                block["text"], chars, words, block["top"], block["bottom"]
            )
            informed_instances = extract_informed_instances(
                chars, block["top"], block["bottom"]
            )

            responsibilities = []
            for inst in action_instances + informed_instances:
                role = nearest_role(page_headers, inst["x0"])
                responsibilities.append(Responsibility(
                    role=role if role else "unresolved",
                    action=inst["action"],
                    level=inst["level"],
                    footnote_refs=inst["footnote_refs"]
                ))

            enriched[identifier] = {
                "id": identifier,
                "node_type": get_node_type(identifier),
                "chapter": get_chapter(identifier),
                "process_id": get_process_id(identifier),
                "parent_task_id": get_parent_task_id(identifier),
                "title": title,
                "page": page_index,
                "responsibilities": responsibilities,
                "references": references,
            }

    all_ids = set(process_titles) | all_task_child_ids
    chapters = sorted({get_chapter(i) for i in all_ids if get_chapter(i)})

    nodes = {}

    for chapter in chapters:
        nodes[chapter] = Node(
            id=chapter,
            node_type="chapter",
            chapter=chapter,
            children=get_children(chapter, all_ids),
            synthetic=True,
        )

    for identifier, title in process_titles.items():
        nodes[identifier] = Node(
            id=identifier,
            node_type="process",
            chapter=get_chapter(identifier),
            children=get_children(identifier, all_ids),
            title=title,
        )

    for identifier in all_task_child_ids:
        data = enriched[identifier]
        nodes[identifier] = Node(
            id=data["id"],
            node_type=data["node_type"],
            chapter=data["chapter"],
            process_id=data["process_id"],
            parent_task_id=data["parent_task_id"],
            children=get_children(identifier, all_ids),
            title=data["title"],
            page=data["page"],
            responsibilities=data["responsibilities"],
            references=data["references"],
        )

    return nodes

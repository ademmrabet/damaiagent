# Merges physical PDF rows into one text block per task/child_task.
#
# v1 BUG, confirmed against real page 21 of the DAM (tasks 2.311 /
# 2.312.1): when a task's title wraps onto a line that lands AFTER its
# actions row but immediately BEFORE the next task's bare identifier
# row, v1 misread that trailing wrapped line as "floating title text
# for the upcoming task" and stole it - producing 2.312.1's stored
# title "agreement for Signature Signature of Financing Agreements
# for..." where "agreement for Signature" actually belongs to 2.311,
# not 2.312.1.
#
# Root cause: v1 decided whether a stray line belonged to "the task
# that follows" using ONLY a look-ahead check (is the next row a bare
# identifier?) - it never checked whether a task was already open and
# waiting for exactly this kind of trailing continuation.
#
# Fix, v1: only apply the "this belongs to the next identifier"
# look-ahead when `current_task is None`. That closed the 2.311 case
# above, but a second real example (3.225 -> 3.226, chapter 3) proved
# it wasn't sufficient: 3.225 is a "redirect" task whose entire row
# ("Communication to Government Refer to Activities 2.114 - 2.117 in
# Section 2.") is grammatically complete and PDF-authored with a
# terminating period - and 3.226's title genuinely starts on the very
# next line, before 3.226's own identifier row appears. current_task
# (3.225) was still "open" by the code's bookkeeping, so the v1 fix
# wrongly glued 3.226's first title line onto 3.225.
#
# Fix, v2: a currently-open task is only treated as "still accepting
# stray lines" if its accumulated text does NOT already end in a
# period. A trailing period is the PDF's own signal that the row is a
# finished sentence (this DAM only seems to terminate text that way
# for these redirect/"Refer to..." rows) - once seen, further stray
# lines go through the same look-ahead check as the "nothing open"
# case, instead of being blindly attached.
#
# Fix, v3: a real screenshot of page 12 found a THIRD variant neither
# v1 nor v2 caught. Task 2.126's entire title+actions ("Quarterly
# Mission program ( i ) I C C R A ( i )") sit on ONE row, right before
# 2.126's own bare identifier row - textbook title-above-identifier.
# But current_task (2.125) was still open, hadn't seen a period, so
# v2's rule attached it to 2.125 anyway. The missing signal: 2.125
# had ALREADY consumed its own actions row earlier. A task's actions
# normally appear once; a stray line carrying a fresh batch of action
# codes on top of a task that already has some is a much stronger
# sign of "this is actually the next task" than punctuation is.
#
# That signal is deliberately narrower than "line contains any action
# code": it only fires when the line ALSO has real prose before the
# first action code (like "Quarterly Mission program" before "( i )").
# A bare trailing line like "( i )" with nothing in front of it is an
# extremely common, completely normal pattern - the informed marker or
# a footnote digit landing on its own row right after a task's main
# action row - and must still attach to the currently open task, not
# get diverted. Without this narrowing, the v3 rule would have wrongly
# hijacked every task that has that (very common) trailing-row shape.

import re

from parsing.metadata import ACTION_PATTERN, NOTE_PATTERN

SECTION_PATTERN = re.compile(r"^\d+\.\d\s+[A-Z]")
NOTES_PATTERN = re.compile(r"^Notes\s+on", re.IGNORECASE)
IDENTIFIER_PATTERN = re.compile(r"^\d+(?:\.\d+)+$")

# threshold_variant sub-items (found via screenshot: 2.513.3 -> (a)/(b)/
# (c) by loan amount, 53 real occurrences across the doc, mostly
# procurement threshold tables). The PDF only ever prints the bare
# "(a)", never the full id - this has to be reconstructed from
# whichever child_task was most recently opened.
#
# Deliberately tight, no internal spaces: "(a)" not "( a )". The
# informed marker always extracts as "( i )" with spaces (three
# separate PDF characters joined by row-building), so this pattern
# doesn't collide with it in practice. Excluding the letter "i"
# outright anyway, as a defensive belt-and-braces in case a table ever
# has a 9th lettered item and pdfplumber happens to render it tight.
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
    last_child_task_id = None  # for reconstructing threshold_variant ids

    def open_task(line, row):
        nonlocal pending_title

        text = line
        if pending_title:
            # identifier must stay first - get_identifier() anchors
            # to the start of the string.
            text = line + " " + pending_title
            pending_title = None

        return {"text": text, "top": row["top"], "bottom": row["bottom"]}

    def close_task():
        nonlocal current_task
        if current_task:
            blocks.append(current_task)
            current_task = None

    def attach(line, row):
        # Append a stray continuation line to whichever task is
        # currently open. Callers only invoke this when current_task
        # is truthy.
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

        # --- threshold_variant: bare "(a)"/"(b)"/... label, id has to
        # be reconstructed from whichever child_task opened last. Never
        # ambiguous with anything else on the page, so it always closes
        # whatever's open and starts fresh - no look-ahead needed.
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

        # --- continuation line (doesn't start with a bare identifier) ---
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
                # A task is open, hasn't been signaled as finished
                # (no trailing period, and not "receiving a second
                # batch of actions") - this line belongs to IT.
                attach(line, row)
                continue

            # Either nothing is open, or what's open looks finished -
            # in both cases check whether the very next row is a bare
            # identifier with nothing else on it, meaning this line is
            # really the start of THAT task's title.
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
                # Belongs to the upcoming identifier - close out
                # whatever's open first (e.g. the finished 3.225).
                close_task()
                pending_title = line
                continue

            if current_task:
                # Looked "finished" (trailing period) but the next
                # row isn't a clean identifier lead-in after all -
                # safest fallback is still attaching it to what's
                # open rather than silently dropping real text.
                attach(line, row)

            # else: nothing open and no upcoming identifier to hand
            # it to - genuinely orphaned, dropped. Rare; worth a test
            # fixture if it shows up in validation.

            continue

        # --- identifier line ---
        parts = identifier.split(".")

        if len(parts) == 3:
            # child task, e.g. 2.325.1 - always starts a new block
            close_task()
            current_task = open_task(line, row)
            last_child_task_id = identifier
            continue

        if len(parts) == 2:

            try:
                suffix_num = int(parts[1])
            except ValueError:
                # not actually a real identifier (shouldn't normally
                # happen given IDENTIFIER_PATTERN, kept defensive)
                if current_task:
                    attach(line, row)
                continue

            if suffix_num % 10 == 0:
                # process boundary, e.g. 2.220 - closes, emits nothing
                close_task()
                pending_title = None
                continue

            # regular task, e.g. 2.221
            close_task()
            current_task = open_task(line, row)
            continue

        # defensive fallback - shouldn't be reachable given the
        # patterns above, but fail safe rather than silently drop data
        if current_task:
            attach(line, row)

    close_task()

    return blocks

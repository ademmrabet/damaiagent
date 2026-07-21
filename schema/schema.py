from typing import Literal

from pydantic import BaseModel, computed_field


# Order matters here: Node references Responsibility in a type hint,
# so Responsibility (and the other leaf classes) must be defined above it.


class Responsibility(BaseModel):
    """
    One role doing one action on one task. If a role does two different
    actions (e.g. checks AND approves the same task), that's TWO
    Responsibility entries, not one entry with two action letters -
    otherwise a single `level` can't tell you which action it belongs to.
    """

    role: str
    action: str  # single letter: "I", "C", "R", "A", or "( i )" for informed

    # Not every action code carries a level (plain "C" has none, "C1" does).
    # Optional with a real None default, instead of a separate has_level
    # bool - one field, one source of truth, can't disagree with itself.
    level: int | None = None

    # A responsibility can cite zero, one, or several footnotes.
    # int to match Footnote.number below - same type on both ends of the
    # relationship so lookups don't need str/int coercion.
    footnote_refs: list[int] = []


class AuthorityCode(BaseModel):
    """
    Reference data - the DAM's own glossary of what each code means.
    Lives independently of any task; tasks/responsibilities only ever
    hold the short `code` string and look the meaning up here. One
    canonical source, so it can't drift the way authority_codes.json
    and authority_rules.py drifted apart from each other in v1.
    """

    code: str  # "I", "I1", "C3", "A2", etc. - matches Responsibility.action
    level: int | None = None
    meaning: str

    # Confirmed against the real legend (page 48 of the updated PDF):
    # I=black, C=red, R=yellow, A=green, (i)=no fill (italic only).
    # Optional since it's only known for the base letters until the
    # legend itself gets parsed/transcribed - don't fake a color for
    # entries that haven't been confirmed yet.
    color: str | None = None


class Footnote(BaseModel):
    """
    Also reference data, not task-owned - a task points TO a footnote
    via Responsibility.footnote_refs, the footnote doesn't point back.

    ASSUMPTION TO CONFIRM: you said numbering resets "chapter to chapter
    or process to process" - I went with process_id as the scope key
    since it's the finer-grained of the two and a process_id already
    tells you the chapter anyway (e.g. "2.220" -> chapter "2"). If
    numbering actually only resets at the chapter boundary and repeats
    across processes within the same chapter, this should be `chapter`
    instead. Check a couple of real cases in the PDF before we build the
    footnote_parser around this.
    """

    scope: str  # process_id this footnote number is scoped to
    number: int
    text: str


class Node(BaseModel):
    """
    Represents all four levels - chapter, process, task, child_task -
    distinguished by node_type. Chapter/process nodes just carry empty
    title/responsibilities/actions; going with one flexible class for
    now rather than a subclass per type, since splitting later if this
    becomes painful is cheap, and getting the split "right" today isn't
    worth the time against the 9-day budget.
    """

    id: str  # NOT int - real ids are dotted strings like "2.221.1"

    # threshold_variant added after finding 53 real cases (e.g.
    # 2.513.3 -> (a)/(b)/(c) by loan amount) of a child_task having
    # ITS OWN children, letter-labeled rather than numbered. id
    # convention: "2.513.3.a", parent_task_id "2.513.3" - see
    # parsing/hierarchy.py and docs/decisions.md.
    node_type: Literal[
        "chapter", "process", "task", "child_task", "threshold_variant"
    ]

    chapter: str
    process_id: str | None = None
    parent_task_id: str | None = None
    children: list[str] = []

    title: str = ""
    page: int | None = None  # source traceability back to the PDF

    # True only for parents synthesized in modeling because the PDF
    # skipped straight to child ids (e.g. 2.312 never has its own row,
    # only 2.312.1 / 2.312.2 do). Never set this during extraction -
    # the parser stays faithful to what's actually on the page.
    synthetic: bool = False

    responsibilities: list[Responsibility] = []

    # Cross-references to OTHER tasks ("See DAM 2.xxx"), not footnotes.
    # Left unvalidated here on purpose - a reference might point outside
    # your ~50-table scope. Whatever builds graph edges from this later
    # has to check the target actually exists as a node before wiring
    # an edge; this field doesn't guarantee that.
    references: list[str] = []

    @computed_field
    @property
    def has_children(self) -> bool:
        # Derived from `children`, not a separate stored bool - two
        # fields that both mean "does this have children" is exactly
        # the kind of pair that can quietly disagree with itself.
        return len(self.children) > 0

    @computed_field
    @property
    def actions(self) -> list[str]:
        # The aggregate "what actions happen on this task" view you
        # asked for - but computed from responsibilities, not stored
        # and populated separately. Responsibility.action stays the
        # one authoritative source; this is just a convenience read,
        # so it can never drift out of sync with the real data.
        seen: list[str] = []
        for r in self.responsibilities:
            if r.action not in seen:
                seen.append(r.action)
        return seen

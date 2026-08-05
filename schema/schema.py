from typing import Literal

from pydantic import BaseModel, computed_field


class Responsibility(BaseModel):
    """
    One role doing one action on one task. If a role does two different
    actions (e.g. checks AND approves the same task), that's TWO
    Responsibility entries, not one entry with two action letters -
    otherwise a single `level` can't tell you which action it belongs to.
    """

    role: str
    action: str

    level: int | None = None

    footnote_refs: list[int] = []


class AuthorityCode(BaseModel):
    """
    Reference data - the DAM's own glossary of what each code means.
    Lives independently of any task; tasks/responsibilities only ever
    hold the short `code` string and look the meaning up here. One
    canonical source, so it can't drift the way authority_codes.json
    and authority_rules.py drifted apart from each other in v1.
    """

    code: str
    level: int | None = None
    meaning: str

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

    scope: str
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

    id: str

    node_type: Literal[
        "chapter", "process", "task", "child_task", "threshold_variant"
    ]

    chapter: str
    process_id: str | None = None
    parent_task_id: str | None = None
    children: list[str] = []

    title: str = ""
    page: int | None = None

    synthetic: bool = False

    responsibilities: list[Responsibility] = []

    references: list[str] = []

    @computed_field
    @property
    def has_children(self) -> bool:
        return len(self.children) > 0

    @computed_field
    @property
    def actions(self) -> list[str]:
        seen: list[str] = []
        for r in self.responsibilities:
            if r.action not in seen:
                seen.append(r.action)
        return seen

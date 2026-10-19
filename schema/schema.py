from typing import Literal

from pydantic import BaseModel, computed_field


# one role doing one action on one task
class Responsibility(BaseModel):

    role: str
    action: str

    level: int | None = None

    footnote_refs: list[int] = []


# meaning of an action code, stored once as reference data
class AuthorityCode(BaseModel):

    code: str
    level: int | None = None
    meaning: str

    color: str | None = None


# footnote text, scoped to a process
class Footnote(BaseModel):

    scope: str
    number: int
    text: str


# any entry of the matrix: chapter, process, task, child task or variant
class Node(BaseModel):

    id: str

    node_type: Literal["chapter", "process", "task", "child_task", "threshold_variant"]

    chapter: str
    process_id: str | None = None
    parent_task_id: str | None = None
    children: list[str] = []

    title: str = ""
    page: int | None = None

    synthetic: bool = False

    responsibilities: list[Responsibility] = []

    references: list[str] = []

    # true if the node has child ids
    @computed_field
    @property
    def has_children(self) -> bool:
        return len(self.children) > 0

    # distinct actions of the node, in order of appearance
    @computed_field
    @property
    def actions(self) -> list[str]:
        seen: list[str] = []
        for r in self.responsibilities:
            if r.action not in seen:
                seen.append(r.action)
        return seen

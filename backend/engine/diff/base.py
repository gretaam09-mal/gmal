from dataclasses import dataclass
from enum import Enum


class ChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


@dataclass(frozen=True)
class Change:
    """A single, deterministic delta between two engine computations.

    `delta` is only ever set when both `before` and `after` are numeric —
    it is computed here, not by whatever later turns this into prose
    (CONVENTIONS.md rule 1: arithmetic lives in engine/), so P-DIFF-NOTE
    never has to subtract two figures itself.
    """

    field: str
    kind: ChangeKind
    before: object | None
    after: object | None
    delta: object | None = None

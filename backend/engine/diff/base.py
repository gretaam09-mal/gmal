from dataclasses import dataclass
from enum import Enum


class ChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


@dataclass(frozen=True)
class Change:
    """A single, deterministic delta between two engine computations."""

    field: str
    kind: ChangeKind
    before: object | None
    after: object | None

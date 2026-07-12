"""Structured diff between two assumption-value mappings — pure, no I/O.

Powers the override/recompute diff strip (F6) and is the sole source of
the numbers P-DIFF-NOTE's prose is allowed to reference — see
services/diff_note/validator.py.
"""
from __future__ import annotations

from decimal import Decimal

from engine.diff.base import Change, ChangeKind

_NUMERIC_TYPES = (int, float, Decimal)


def compute_assumption_diff(
    old: dict[str, object], new: dict[str, object]
) -> tuple[Change, ...]:
    changes: list[Change] = []
    for key in sorted(set(old) | set(new)):
        has_old = key in old
        has_new = key in new
        before = old.get(key)
        after = new.get(key)
        if has_old and has_new:
            if before == after:
                continue
            delta = (
                after - before
                if isinstance(before, _NUMERIC_TYPES) and isinstance(after, _NUMERIC_TYPES)
                else None
            )
            changes.append(
                Change(field=key, kind=ChangeKind.CHANGED, before=before, after=after, delta=delta)
            )
        elif has_new:
            changes.append(Change(field=key, kind=ChangeKind.ADDED, before=None, after=after))
        else:
            changes.append(Change(field=key, kind=ChangeKind.REMOVED, before=before, after=None))
    return tuple(changes)

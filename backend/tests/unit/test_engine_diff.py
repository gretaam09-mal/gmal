from engine.diff.base import Change, ChangeKind


def test_change_is_immutable() -> None:
    change = Change(field="headline_exposure", kind=ChangeKind.CHANGED, before=100, after=150)
    assert change.kind is ChangeKind.CHANGED
    assert (change.before, change.after) == (100, 150)

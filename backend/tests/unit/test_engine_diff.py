from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from engine.diff import Change, ChangeKind, compute_assumption_diff


def test_change_is_immutable() -> None:
    change = Change(field="headline_exposure", kind=ChangeKind.CHANGED, before=100, after=150)
    assert change.kind is ChangeKind.CHANGED
    assert (change.before, change.after) == (100, 150)


# --- Example-based: the diff shape is the spec, pin it exactly. ---


def test_changed_value_produces_a_change_with_delta():
    old = {"discount_rate_pct": Decimal("5")}
    new = {"discount_rate_pct": Decimal("8")}
    changes = compute_assumption_diff(old, new)
    assert changes == (
        Change(
            field="discount_rate_pct",
            kind=ChangeKind.CHANGED,
            before=Decimal("5"),
            after=Decimal("8"),
            delta=Decimal("3"),
        ),
    )


def test_unchanged_value_produces_no_entry():
    old = {"discount_rate_pct": Decimal("5")}
    new = {"discount_rate_pct": Decimal("5")}
    assert compute_assumption_diff(old, new) == ()


def test_added_key_has_none_before_and_no_delta():
    changes = compute_assumption_diff({}, {"headcount": Decimal("100")})
    assert changes == (
        Change(field="headcount", kind=ChangeKind.ADDED, before=None, after=Decimal("100")),
    )


def test_removed_key_has_none_after_and_no_delta():
    changes = compute_assumption_diff({"headcount": Decimal("100")}, {})
    assert changes == (
        Change(field="headcount", kind=ChangeKind.REMOVED, before=Decimal("100"), after=None),
    )


def test_non_numeric_change_has_no_delta():
    changes = compute_assumption_diff({"source_basis": "estimate"}, {"source_basis": "quoted"})
    assert changes == (
        Change(field="source_basis", kind=ChangeKind.CHANGED, before="estimate", after="quoted"),
    )


def test_entries_are_sorted_by_key_for_determinism():
    old = {"b": Decimal("1"), "a": Decimal("1")}
    new = {"b": Decimal("2"), "a": Decimal("2")}
    changes = compute_assumption_diff(old, new)
    assert [c.field for c in changes] == ["a", "b"]


# --- Property-based: invariants that must hold for any pair of dicts. ---

_keys = st.sampled_from(["a", "b", "c", "d"])
_values = st.one_of(
    st.integers(min_value=-1000, max_value=1000).map(Decimal),
    st.text(min_size=1, max_size=5, alphabet="xyz"),
)
_dicts = st.dictionaries(_keys, _values, max_size=4)


@given(old=_dicts, new=_dicts)
def test_every_change_is_a_real_change(old, new):
    for change in compute_assumption_diff(old, new):
        assert old.get(change.field) != new.get(change.field)


@given(old=_dicts, new=_dicts)
def test_delta_is_only_set_when_both_sides_are_numeric(old, new):
    for change in compute_assumption_diff(old, new):
        both_numeric = isinstance(change.before, Decimal) and isinstance(change.after, Decimal)
        if change.delta is not None:
            assert both_numeric
            assert change.delta == change.after - change.before


@given(mapping=_dicts)
def test_diffing_a_mapping_against_itself_is_empty(mapping):
    assert compute_assumption_diff(mapping, dict(mapping)) == ()


@given(old=_dicts, new=_dicts)
def test_compute_assumption_diff_is_deterministic(old, new):
    assert compute_assumption_diff(old, new) == compute_assumption_diff(dict(old), dict(new))

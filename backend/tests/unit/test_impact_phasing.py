from datetime import date
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from engine.impact.phasing import phase_schedule

# --- Example-based: the phasing shape is the spec, pin it exactly. ---


def test_zero_transition_months_lands_the_full_amount_in_one_period():
    schedule = phase_schedule(
        Decimal("1200"),
        first_obligation_date=date(2027, 3, 1),
        transition_months=0,
        analysis_date=date(2027, 1, 1),
    )
    assert len(schedule) == 1
    assert schedule[0].period == "2027-03"
    assert schedule[0].amount == Decimal("1200")


def test_transition_months_splits_evenly_across_periods():
    schedule = phase_schedule(
        Decimal("1200"),
        first_obligation_date=date(2027, 1, 1),
        transition_months=3,
        analysis_date=date(2027, 1, 1),
    )
    assert [entry.period for entry in schedule] == ["2027-01", "2027-02", "2027-03", "2027-04"]
    assert [entry.amount for entry in schedule] == [Decimal("300")] * 4


def test_missing_first_obligation_date_falls_back_to_analysis_date():
    schedule = phase_schedule(
        Decimal("500"),
        first_obligation_date=None,
        transition_months=0,
        analysis_date=date(2027, 6, 15),
    )
    assert schedule[0].period == "2027-06"


def test_periods_roll_over_year_boundaries():
    schedule = phase_schedule(
        Decimal("300"),
        first_obligation_date=date(2027, 11, 1),
        transition_months=2,
        analysis_date=date(2027, 1, 1),
    )
    assert [entry.period for entry in schedule] == ["2027-11", "2027-12", "2028-01"]


def test_none_total_produces_no_schedule():
    schedule = phase_schedule(
        None,
        first_obligation_date=date(2027, 1, 1),
        transition_months=0,
        analysis_date=date(2027, 1, 1),
    )
    assert schedule == ()


# --- Property-based: invariants that must hold for any total/dates/span. ---

_cents = st.integers(min_value=0, max_value=10_000_000).map(lambda cents: Decimal(cents) / 100)
_transition_months = st.integers(min_value=0, max_value=36)
_years = st.integers(min_value=2020, max_value=2035)
_months = st.integers(min_value=1, max_value=12)


@given(total=_cents, months=_transition_months, year=_years, month=_months)
def test_phased_entries_always_sum_to_the_total(total, months, year, month):
    start = date(year, month, 1)
    schedule = phase_schedule(
        total, first_obligation_date=start, transition_months=months, analysis_date=start
    )
    assert sum(entry.amount for entry in schedule) == total


@given(total=_cents, months=_transition_months, year=_years, month=_months)
def test_phased_entry_count_matches_transition_span(total, months, year, month):
    start = date(year, month, 1)
    schedule = phase_schedule(
        total, first_obligation_date=start, transition_months=months, analysis_date=start
    )
    assert len(schedule) == months + 1


@given(total=_cents, months=_transition_months, year=_years, month=_months)
def test_phase_schedule_is_deterministic(total, months, year, month):
    start = date(year, month, 1)
    first = phase_schedule(
        total, first_obligation_date=start, transition_months=months, analysis_date=start
    )
    second = phase_schedule(
        total, first_obligation_date=start, transition_months=months, analysis_date=start
    )
    assert first == second

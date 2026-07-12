from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from engine.impact.present_value import discount_to_present_value

# --- Example-based: the PV maths is the spec, pin it exactly. ---


def test_zero_discount_rate_leaves_the_nominal_sum_unchanged():
    amounts = [Decimal("100"), Decimal("200"), Decimal("300")]
    assert discount_to_present_value(amounts, discount_rate_pct=Decimal("0")) == Decimal("600")


def test_positive_discount_rate_discounts_later_periods_more():
    amounts = [Decimal("100"), Decimal("100")]
    pv = discount_to_present_value(amounts, discount_rate_pct=Decimal("10"))
    assert pv == Decimal("100") + (Decimal("100") / Decimal("1.1"))


def test_fx_rate_scales_the_result():
    amounts = [Decimal("100")]
    gbp = discount_to_present_value(amounts, discount_rate_pct=Decimal("0"), fx_rate=Decimal("1"))
    usd_equivalent = discount_to_present_value(
        amounts, discount_rate_pct=Decimal("0"), fx_rate=Decimal("1.25")
    )
    assert usd_equivalent == gbp * Decimal("1.25")


def test_empty_schedule_has_zero_present_value():
    assert discount_to_present_value([], discount_rate_pct=Decimal("5")) == Decimal("0")


# --- Property-based: invariants that must hold for any schedule/rate/fx. ---

_amounts = st.lists(
    st.integers(min_value=0, max_value=1_000_000).map(lambda cents: Decimal(cents) / 100),
    min_size=0,
    max_size=24,
)
_rates = st.integers(min_value=0, max_value=5000).map(lambda bp: Decimal(bp) / 100)


@given(amounts=_amounts, rate=_rates)
def test_present_value_never_exceeds_the_nominal_sum_when_rate_is_non_negative(amounts, rate):
    pv = discount_to_present_value(amounts, discount_rate_pct=rate)
    assert pv <= sum(amounts)


@given(amounts=_amounts, low_rate=_rates, high_rate=_rates)
def test_present_value_is_monotonically_non_increasing_in_the_discount_rate(
    amounts, low_rate, high_rate
):
    small, big = sorted((low_rate, high_rate))
    pv_small_rate = discount_to_present_value(amounts, discount_rate_pct=small)
    pv_big_rate = discount_to_present_value(amounts, discount_rate_pct=big)
    assert pv_big_rate <= pv_small_rate


_fx_rates = st.integers(min_value=1, max_value=500).map(lambda cents: Decimal(cents) / 100)


@given(amounts=_amounts, rate=_rates, fx=_fx_rates)
def test_present_value_is_deterministic(amounts, rate, fx):
    first = discount_to_present_value(amounts, discount_rate_pct=rate, fx_rate=fx)
    second = discount_to_present_value(list(amounts), discount_rate_pct=rate, fx_rate=fx)
    assert first == second

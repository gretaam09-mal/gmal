"""F10: the monthly metrics report — aggregates MetricsEvent rows (plus
the used-in-IC tag straight off Memo) into board-ready numbers without
any manual collation. Pure aggregation over already-recorded events; no
new measurement happens here — see services/metrics.py and
services/onboarding_metrics.py for where each event is actually written.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import Memo, MetricsEvent, Tenant
from db.session import set_rls_context
from services.metrics import (
    ASSUMPTION_OVERRIDDEN_EVENT,
    EXPOSURE_LIST_GENERATED_EVENT,
    MEMO_APPROVED_EVENT,
    REVIEW_COMPLETED_EVENT,
)
from services.onboarding_metrics import ONBOARDING_COMPLETED_EVENT


@dataclass(frozen=True)
class MonthlyMetricsReport:
    period_start: datetime
    period_end: datetime
    time_to_exposure_list_minutes_avg: float | None
    time_to_approved_memo_minutes_avg: float | None
    review_minutes_avg: float | None
    onboarding_hours_avg: float | None
    override_count: int
    memos_approved_count: int
    used_in_ic_count: int


def _period_bounds(*, year: int, month: int) -> tuple[datetime, datetime]:
    period_start = datetime(year, month, 1, tzinfo=UTC)
    period_end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=UTC)
    )
    return period_start, period_end


def _events_in_period(
    session: Session, event_name: str, period_start: datetime, period_end: datetime
) -> list[MetricsEvent]:
    return list(
        session.execute(
            select(MetricsEvent).where(
                MetricsEvent.event_name == event_name,
                MetricsEvent.created_at >= period_start,
                MetricsEvent.created_at < period_end,
            )
        ).scalars()
    )


def _avg_property(events: list[MetricsEvent], key: str) -> float | None:
    values = [
        events_value
        for event in events
        if (events_value := event.properties.get(key)) is not None
    ]
    return round(mean(values), 2) if values else None


def _used_in_ic_count_across_tenants(
    session: Session, *, period_start: datetime, period_end: datetime
) -> int:
    """Memo.used_in_ic is a tenant-scoped, RLS-protected field, so a
    board-wide count means switching this connection's RLS context
    tenant-by-tenant (same approach as services.sources.sweep's
    cross-tenant memo flagging) — no single session can see every
    tenant's memos at once."""
    total = 0
    tenants = session.execute(select(Tenant)).scalars().all()
    for tenant in tenants:
        set_rls_context(session, tenant.id, None)
        total += session.execute(
            select(func.count())
            .select_from(Memo)
            .where(
                Memo.used_in_ic.is_(True),
                Memo.created_at >= period_start,
                Memo.created_at < period_end,
            )
        ).scalar()
    return total


def generate_monthly_metrics_report(
    session: Session, *, year: int, month: int
) -> MonthlyMetricsReport:
    period_start, period_end = _period_bounds(year=year, month=month)

    exposure_events = _events_in_period(
        session, EXPOSURE_LIST_GENERATED_EVENT, period_start, period_end
    )
    approved_events = _events_in_period(session, MEMO_APPROVED_EVENT, period_start, period_end)
    review_events = _events_in_period(session, REVIEW_COMPLETED_EVENT, period_start, period_end)
    onboarding_events = _events_in_period(
        session, ONBOARDING_COMPLETED_EVENT, period_start, period_end
    )
    override_events = _events_in_period(
        session, ASSUMPTION_OVERRIDDEN_EVENT, period_start, period_end
    )

    return MonthlyMetricsReport(
        period_start=period_start,
        period_end=period_end,
        time_to_exposure_list_minutes_avg=_avg_property(
            exposure_events, "time_to_exposure_list_minutes"
        ),
        time_to_approved_memo_minutes_avg=_avg_property(
            approved_events, "time_to_approved_memo_minutes"
        ),
        review_minutes_avg=_avg_property(review_events, "review_minutes"),
        onboarding_hours_avg=_avg_property(onboarding_events, "onboarding_hours"),
        override_count=len(override_events),
        memos_approved_count=len(approved_events),
        used_in_ic_count=_used_in_ic_count_across_tenants(
            session, period_start=period_start, period_end=period_end
        ),
    )

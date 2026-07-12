"""F10 — the monthly metrics report. Staff-only (require_staff), like
api/routes/admin_instruments.py: this aggregates board metrics across
every tenant, which is never something a workspace-scoped route exposes.
"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_raw_session, require_staff
from api.schemas import MonthlyMetricsReportOut
from db.models import User
from services.metrics_report import generate_monthly_metrics_report

router = APIRouter(prefix="/admin", tags=["admin-metrics"])


@router.get("/metrics/monthly-report", response_model=MonthlyMetricsReportOut)
async def get_monthly_metrics_report(
    year: int | None = None,
    month: int | None = None,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> MonthlyMetricsReportOut:
    """Defaults to the current month — a monthly board report a human
    generates by pointing a browser at this URL, no manual collation."""
    today = date.today()
    report = generate_monthly_metrics_report(
        session, year=year or today.year, month=month or today.month
    )
    return MonthlyMetricsReportOut(
        period_start=report.period_start,
        period_end=report.period_end,
        time_to_exposure_list_minutes_avg=report.time_to_exposure_list_minutes_avg,
        time_to_approved_memo_minutes_avg=report.time_to_approved_memo_minutes_avg,
        review_minutes_avg=report.review_minutes_avg,
        onboarding_hours_avg=report.onboarding_hours_avg,
        override_count=report.override_count,
        memos_approved_count=report.memos_approved_count,
        used_in_ic_count=report.used_in_ic_count,
    )

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, PrimaryKeyMixin, TenantScopedMixin, TimestampMixin
from db.models.enums import AnalysisItemOutcome, AnalysisStatus


class Analysis(Base, PrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """One run of the engine over a specific entity profile version.

    discount_rate_pct/fx_rate/base_currency are F5's declared (never
    computed or fetched live) present-value settings for this run — see
    engine/impact/present_value.py. Recorded on the Analysis itself so a
    later memo can show exactly what assumptions produced its numbers.
    """

    __tablename__ = "analyses"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    entity_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity_profiles.id"), nullable=False, index=True
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status"), nullable=False, default=AnalysisStatus.PENDING
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    discount_rate_pct: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False, default=0)
    fx_rate: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=1)
    base_currency: Mapped[str] = mapped_column(String, nullable=False, default="GBP")


class AnalysisItem(Base, PrimaryKeyMixin, TenantScopedMixin):
    """One predicate's outcome within an analysis — output of engine/, not
    I/O. Append-only (DB trigger, see the instrument_onboarding_immutability
    migration): an analysis is computed once and never edited in place.

    `outcome` is the tri-state engine/predicates.evaluate_predicate result
    (BINDS / DOES_NOT_BIND / AMBIGUOUS); `missing_field_keys` is only
    non-empty when AMBIGUOUS, naming the profile field(s) that would
    resolve it. `rationale` is assembled deterministically by
    engine/rationale — no AI at analysis time (CONVENTIONS.md rule 1).
    `amount` is only ever set when outcome is BINDS and the obligation has
    a cost template; it comes from engine/impact, never composed here — it
    is F4's single "likely" point value, kept for backwards compatibility.
    `impact_low`/`impact_high` are F5's best/worst range bounds from
    engine/impact/range.py; `present_value` is the same range's likely
    figure discounted per the parent Analysis's discount_rate_pct/fx_rate
    (engine/impact/present_value.py). `phased_schedule` is the per-period
    breakdown from engine/impact/phasing.py —
    `[{"period": "2027-01", "amount": N}, ...]` — whose entries always sum
    to `amount` (a property test enforces this).
    """

    __tablename__ = "analysis_items"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=False, index=True
    )
    predicate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predicates.id"), nullable=False
    )
    outcome: Mapped[AnalysisItemOutcome] = mapped_column(
        Enum(AnalysisItemOutcome, name="analysis_item_outcome"), nullable=False
    )
    missing_field_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    rationale: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    impact_low: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    impact_high: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    present_value: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    phased_schedule: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    currency: Mapped[str] = mapped_column(String, nullable=False, default="GBP")
    engine_version: Mapped[str] = mapped_column(String, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

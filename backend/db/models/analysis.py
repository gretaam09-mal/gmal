import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, PrimaryKeyMixin, TenantScopedMixin, TimestampMixin
from db.models.enums import AnalysisItemOutcome, AnalysisStatus


class Analysis(Base, PrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """One run of the engine over a specific entity profile version."""

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
    a cost template; it comes from engine/impact, never composed here.
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
    currency: Mapped[str] = mapped_column(String, nullable=False, default="GBP")
    engine_version: Mapped[str] = mapped_column(String, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, CreatedAtMixin, PrimaryKeyMixin, TenantScopedMixin
from db.models.enums import SourceDocumentStatus, SweepRunStatus


class ForecastLogEntry(Base, PrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin):
    """Append-only record of a forecast the engine produced, for later diffing."""

    __tablename__ = "forecast_log"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=True
    )
    predicate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predicates.id"), nullable=True
    )
    forecast_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class SourceDocument(Base, PrimaryKeyMixin, TenantScopedMixin):
    """An ingested document (filing, upload) backing an entity profile."""

    __tablename__ = "source_documents"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    entity_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity_profiles.id"), nullable=True
    )
    doc_type: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[SourceDocumentStatus] = mapped_column(
        Enum(SourceDocumentStatus, name="source_document_status"),
        nullable=False,
        default=SourceDocumentStatus.UPLOADED,
    )
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SweepRun(Base, PrimaryKeyMixin, CreatedAtMixin):
    """A run of F9's daily source sweep.

    Platform-wide like Instrument/InstrumentVersion (a sweep checks the
    curated official sources shared by every tenant, not one tenant's
    data), so — like MetricsEvent/ErrorRegisterEntry — this carries a
    nullable tenant_id/workspace_id instead of TenantScopedMixin and
    carries no RLS policy; see the sweep_runs_platform_wide migration.
    """

    __tablename__ = "sweep_runs"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True
    )
    run_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[SweepRunStatus] = mapped_column(
        Enum(SweepRunStatus, name="sweep_run_status"),
        nullable=False,
        default=SweepRunStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class CuratedSource(Base, PrimaryKeyMixin, CreatedAtMixin):
    """F9: a curated official source the daily sweep watches for changes
    (FCA Handbook, PRA Rulebook, legislation.gov.uk, UK Parliament API).

    Platform-wide reference data, like Instrument/InstrumentVersion —
    not tenant data, so no TenantScopedMixin and no RLS policy.
    `instrument_id` links a source to the Instrument its content feeds;
    left null until a human maps a newly curated source to an instrument
    via the onboarding workbench.
    """

    __tablename__ = "curated_sources"

    key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=True
    )
    last_content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    last_swept_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MetricsEvent(Base, PrimaryKeyMixin, CreatedAtMixin):
    """A product metrics event. tenant_id/workspace_id are nullable to allow
    system-level events; anything workspace-scoped still carries both."""

    __tablename__ = "metrics_events"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True
    )
    event_name: Mapped[str] = mapped_column(String, nullable=False)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ErrorRegisterEntry(Base, PrimaryKeyMixin, CreatedAtMixin):
    """An operational error worth tracking to resolution.

    F10: this is specifically for *post-approval* errors — something
    that turned out to be wrong in a memo a client already received —
    so root_cause/affected_workspace_ids/disclosure_* exist to support
    the disclosure obligation that follows, not just internal triage.
    """

    __tablename__ = "error_register"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(String, nullable=True)
    affected_workspace_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    """Every workspace (client) this error is known to have reached —
    deliberately a JSONB list of ids rather than a join table, since this
    register logs a small, staff-curated volume of incidents, not a
    high-cardinality relation."""
    disclosure_note: Mapped[str | None] = mapped_column(String, nullable=True)
    disclosure_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Report(Base, PrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin):
    """A generated, distributable export of a memo version."""

    __tablename__ = "reports"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    memo_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memo_versions.id"), nullable=True
    )
    report_type: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    generated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

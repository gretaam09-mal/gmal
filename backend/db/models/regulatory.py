import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, BitemporalMixin, PrimaryKeyMixin
from db.models.enums import PredicateStatus

# Tables in this module are shared reference data — regulatory instruments,
# not tenant data — so they deliberately do NOT carry tenant_id
# (CONVENTIONS.md rule #3 governs tenant data; this is the reference
# material every tenant's engine/ computations read from). They are
# bitemporal because the law itself changes over time and Provision must
# be able to say "what did we believe the rule was on date X". Per
# BitemporalMixin's own contract, none of these rows are ever UPDATEd in
# place — a correction closes the old row's valid_to and inserts a new
# one. See services/instrument_onboarding.py and the
# instrument_onboarding_immutability migration for the DB-level backstop
# once an obligation/predicate is approved.


class Instrument(Base, PrimaryKeyMixin, BitemporalMixin):
    """A piece of regulation (an Act, a Regulation, a statutory instrument)."""

    __tablename__ = "instruments"

    title: Mapped[str] = mapped_column(String, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String, nullable=False, default="UK")
    kind: Mapped[str] = mapped_column(String, nullable=False)
    citation: Mapped[str | None] = mapped_column(String, nullable=True)
    in_flight: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """Still being drafted/consulted on rather than settled law — gates F5's
    scenario outcome-weighting (services/scenarios.py): an in-flight
    instrument's impact range is probability-weighted across as-drafted/
    amended/delayed scenarios (see forecast_log entries with
    forecast_type="scenario_probability"); a settled instrument always
    uses a single as-drafted scenario at probability 1.0."""


class InstrumentVersion(Base, PrimaryKeyMixin, BitemporalMixin):
    """A published version/consolidation of an instrument.

    `content_hash` (sha256 of `raw_text`) is what F3's ingestion step
    hashes+versions on — re-ingesting identical text is a no-op rather
    than a duplicate version (see services/instrument_onboarding.py).
    """

    __tablename__ = "instrument_versions"

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False, index=True
    )
    version_label: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(String, nullable=False)


class Clause(Base, PrimaryKeyMixin, BitemporalMixin):
    """A single clause within an instrument version — citations always
    point at one of these, never at a whole instrument."""

    __tablename__ = "clauses"

    instrument_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instrument_versions.id"), nullable=False, index=True
    )
    clause_ref: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Obligation(Base, PrimaryKeyMixin, BitemporalMixin):
    """A discrete obligation derived from a clause.

    `fields` holds the who/what/when/threshold/enforcer structure P-EXTRACT
    (or a human editor) produced — each entry is
    `{"value": ..., "clause_ref": "...", "confidence": 0-100}`, e.g.
    `{"who": {"value": "authorised firms", "clause_ref": "s.2(1)",
    "confidence": 92}, ...}`. See services/extraction/schemas.py for the
    Pydantic shape validated before anything lands here.

    `approved` gates F4 entirely: nothing reaches a client-facing analysis
    unless approved is True (services/analyses.py only ever queries
    approved obligations' predicates). Once True, the row is immutable
    (DB trigger) — a correction is a new Obligation version with the
    prior one's valid_to closed, not a mutation.
    """

    __tablename__ = "obligations"

    clause_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(String, nullable=False)
    obligation_type: Mapped[str] = mapped_column(String, nullable=False)
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extracted_by: Mapped[str] = mapped_column(String, nullable=False, default="human")
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Predicate(Base, PrimaryKeyMixin, BitemporalMixin):
    """A structured, pure-evaluable condition consumed by engine/predicates.

    `expression` is a JSON-serialisable structure the engine interprets —
    never code, never something an LLM writes at analysis time. A
    P-PREDICATE-ASSIST draft (`drafted_by_ai=True`) always starts as
    `status=DRAFT`; only a human approval transitions it to APPROVED
    (services/predicate_assist.py never writes APPROVED itself). Only
    APPROVED predicates are evaluated by F4.
    """

    __tablename__ = "predicates"

    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=False, index=True
    )
    predicate_key: Mapped[str] = mapped_column(String, nullable=False)
    expression: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[PredicateStatus] = mapped_column(
        Enum(PredicateStatus, name="predicate_status"),
        nullable=False,
        default=PredicateStatus.DRAFT,
    )
    drafted_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CostTemplate(Base, PrimaryKeyMixin, BitemporalMixin):
    """A structured formula consumed by engine/impact to quantify a match.

    `drivers` names the facts (profile field keys) the formula reads —
    e.g. `[{"key": "scale.employee_count", "label": "Employee count"}]` —
    so engine/impact and the admin UI both know what to plug in without
    guessing from `formula`. `source_basis` and `maturity_tier` record
    where the numbers came from and how much to trust them (e.g.
    "vendor quote" / "quoted", "expert estimate" / "rough").
    """

    __tablename__ = "cost_templates"

    obligation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    drivers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    """Each entry may carry an optional "category" — one of the six named
    driver categories F5 asks for (systems, staffing, external_advice,
    reporting_effort, capital, restricted_revenue) — purely for grouping
    in the memo's waterfall; engine/impact doesn't interpret it."""
    formula: Mapped[dict] = mapped_column(JSONB, nullable=False)
    """`{"base": N, "terms": [{"driver": key, "rate": r}, ...],
    "range": {"low_multiplier": 0.8, "high_multiplier": 1.3}}` — `range`
    is optional (see engine/impact/range.py's defaults) and is how a
    single point formula also produces a best/worst spread."""
    currency: Mapped[str] = mapped_column(String, nullable=False, default="GBP")
    source_basis: Mapped[str] = mapped_column(String, nullable=False)
    maturity_tier: Mapped[str] = mapped_column(String, nullable=False)
    first_obligation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    """When the cost first applies — declared by the staff member
    attaching the template (like a predicate, never inferred by P-EXTRACT
    from clause text), so engine/impact can time-phase it. Null means
    "immediate/ongoing from the moment the obligation binds"."""
    transition_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """How many months the cost phases in over, starting at
    first_obligation_date — 0 means the full amount lands in one period."""

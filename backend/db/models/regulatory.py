import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, BitemporalMixin, PrimaryKeyMixin

# Tables in this module are shared reference data — regulatory instruments,
# not tenant data — so they deliberately do NOT carry tenant_id
# (CONVENTIONS.md rule #3 governs tenant data; this is the reference
# material every tenant's engine/ computations read from). They are
# bitemporal because the law itself changes over time and Provision must
# be able to say "what did we believe the rule was on date X".


class Instrument(Base, PrimaryKeyMixin, BitemporalMixin):
    """A piece of regulation (an Act, a Regulation, a statutory instrument)."""

    __tablename__ = "instruments"

    title: Mapped[str] = mapped_column(String, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String, nullable=False, default="UK")
    kind: Mapped[str] = mapped_column(String, nullable=False)
    citation: Mapped[str | None] = mapped_column(String, nullable=True)


class InstrumentVersion(Base, PrimaryKeyMixin, BitemporalMixin):
    """A published version/consolidation of an instrument."""

    __tablename__ = "instrument_versions"

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False, index=True
    )
    version_label: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)


class Clause(Base, PrimaryKeyMixin, BitemporalMixin):
    """A single clause within an instrument version."""

    __tablename__ = "clauses"

    instrument_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instrument_versions.id"), nullable=False, index=True
    )
    clause_ref: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)


class Obligation(Base, PrimaryKeyMixin, BitemporalMixin):
    """A discrete obligation derived from a clause."""

    __tablename__ = "obligations"

    clause_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(String, nullable=False)
    obligation_type: Mapped[str] = mapped_column(String, nullable=False)


class Predicate(Base, PrimaryKeyMixin, BitemporalMixin):
    """A structured, pure-evaluable condition consumed by engine/predicates.

    `expression` is a JSON-serialisable structure the engine interprets —
    never code, never something an LLM writes at analysis time.
    """

    __tablename__ = "predicates"

    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=False, index=True
    )
    predicate_key: Mapped[str] = mapped_column(String, nullable=False)
    expression: Mapped[dict] = mapped_column(JSONB, nullable=False)


class CostTemplate(Base, PrimaryKeyMixin, BitemporalMixin):
    """A structured formula consumed by engine/impact to quantify a match."""

    __tablename__ = "cost_templates"

    obligation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=True, index=True
    )
    formula: Mapped[dict] = mapped_column(JSONB, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="GBP")

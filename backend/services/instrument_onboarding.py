"""F3 orchestration: the DB-touching half of the instrument-onboarding
workbench. services/ingestion (pure text work) and engine/predicates
(pure evaluation) do the actual logic; this module wires them to
Instrument/Clause/Obligation/Predicate/CostTemplate rows.

Instruments/clauses/obligations/predicates/cost_templates are shared
reference data, not tenant data (see db/models/regulatory.py) — no
tenant scoping here, that's not a gap, see CONVENTIONS.md rule #3's own
scope ("tenant data").

Mutation rules (CONVENTIONS.md rule #2, enforced again by DB trigger —
see the instrument_onboarding_immutability migration):
  - An Obligation/Predicate may be edited freely (plain UPDATE) while
    still a draft (approved=False / status=DRAFT) — that's normal
    review, not a "correction to an approved record".
  - The moment it's approved, it's frozen. Any further correction must
    go through correct_obligation, which closes the old row's valid_to
    and inserts a new one — never a mutation.
  - CostTemplate is always append-only; attach_cost_template always
    inserts a new version and closes the previous current one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Clause, CostTemplate, Instrument, InstrumentVersion, Obligation, Predicate
from db.models.enums import PredicateStatus
from engine.predicates.dsl import validate_expression
from services.extraction.provider import ExtractionProvider
from services.ingestion import hash_text, segment_clauses
from services.onboarding_metrics import maybe_record_onboarding_completion
from services.predicate_assist.provider import PredicateAssistProvider


class ObligationLockedError(Exception):
    """Raised when the caller tries to edit an already-approved obligation
    directly instead of going through correct_obligation."""


class PredicateLockedError(Exception):
    """Same as ObligationLockedError, for predicates."""


# --- Instrument ingestion ---------------------------------------------------


def ingest_instrument(
    session: Session,
    *,
    title: str,
    jurisdiction: str,
    kind: str,
    citation: str | None,
    version_label: str,
    source_url: str | None,
    raw_text: str,
    in_flight: bool = False,
) -> InstrumentVersion:
    now = datetime.now(UTC)
    instrument = Instrument(
        title=title,
        jurisdiction=jurisdiction,
        kind=kind,
        citation=citation,
        in_flight=in_flight,
        valid_from=now,
    )
    session.add(instrument)
    session.flush()

    version = InstrumentVersion(
        instrument_id=instrument.id,
        version_label=version_label,
        source_url=source_url,
        content_hash=hash_text(raw_text),
        raw_text=raw_text,
        valid_from=now,
    )
    session.add(version)
    session.flush()

    for segment in segment_clauses(raw_text):
        session.add(
            Clause(
                instrument_version_id=version.id,
                clause_ref=segment.clause_ref,
                text=segment.text,
                ordinal=segment.ordinal,
                valid_from=now,
            )
        )
    session.flush()
    return version


def ingest_new_instrument_version(
    session: Session,
    *,
    instrument: Instrument,
    version_label: str,
    source_url: str | None,
    raw_text: str,
) -> InstrumentVersion:
    """F9: a curated source's content changed — close the instrument's
    current version's valid_to and record a fresh one with its own
    clauses, the same close-then-insert pattern correct_obligation uses.
    The new version's obligations/predicates start unapproved, so it
    surfaces in the onboarding workbench exactly like a first ingest."""
    now = datetime.now(UTC)
    current = session.execute(
        select(InstrumentVersion).where(
            InstrumentVersion.instrument_id == instrument.id,
            InstrumentVersion.valid_to.is_(None),
        )
    ).scalar_one()
    current.valid_to = now
    session.flush()

    version = InstrumentVersion(
        instrument_id=instrument.id,
        version_label=version_label,
        source_url=source_url,
        content_hash=hash_text(raw_text),
        raw_text=raw_text,
        valid_from=now,
    )
    session.add(version)
    session.flush()

    for segment in segment_clauses(raw_text):
        session.add(
            Clause(
                instrument_version_id=version.id,
                clause_ref=segment.clause_ref,
                text=segment.text,
                ordinal=segment.ordinal,
                valid_from=now,
            )
        )
    session.flush()
    return version


def list_clauses(session: Session, instrument_version_id: uuid.UUID) -> list[Clause]:
    return list(
        session.execute(
            select(Clause)
            .where(Clause.instrument_version_id == instrument_version_id)
            .order_by(Clause.ordinal)
        ).scalars()
    )


# --- Obligation extraction, review, approval --------------------------------


def extract_obligation(
    session: Session, *, clause: Clause, instrument_title: str, provider: ExtractionProvider
) -> Obligation:
    """Runs P-EXTRACT (or its fixture stand-in) and persists the result as
    an unapproved draft — never as anything a client-facing analysis
    could read (see services/analyses.py, which only ever queries
    approved obligations)."""
    extracted = provider.extract(
        clause_text=clause.text, clause_ref=clause.clause_ref, instrument_title=instrument_title
    )
    obligation = Obligation(
        clause_id=clause.id,
        summary=extracted.summary,
        obligation_type=extracted.obligation_type,
        fields=extracted.to_fields_json(),
        confidence=extracted.confidence,
        extracted_by="P-EXTRACT v1",
        approved=False,
        valid_from=datetime.now(UTC),
    )
    session.add(obligation)
    session.flush()
    return obligation


def update_obligation(
    session: Session,
    *,
    obligation: Obligation,
    summary: str | None = None,
    obligation_type: str | None = None,
    fields: dict[str, Any] | None = None,
    confidence: int | None = None,
) -> Obligation:
    """A reviewer's correction to a still-draft obligation. Plain UPDATE —
    legitimate pre-approval editing, not a "correction to an approved
    record" (see module docstring)."""
    if obligation.approved:
        raise ObligationLockedError(
            f"Obligation {obligation.id} is already approved — use correct_obligation instead"
        )
    if summary is not None:
        obligation.summary = summary
    if obligation_type is not None:
        obligation.obligation_type = obligation_type
    if fields is not None:
        obligation.fields = fields
    if confidence is not None:
        obligation.confidence = confidence
    session.flush()
    return obligation


def approve_obligation(
    session: Session, *, obligation: Obligation, approved_by_user_id: uuid.UUID
) -> Obligation:
    if obligation.approved:
        raise ObligationLockedError(f"Obligation {obligation.id} is already approved")
    obligation.approved = True
    obligation.approved_by_user_id = approved_by_user_id
    obligation.approved_at = datetime.now(UTC)
    session.flush()

    clause = session.get(Clause, obligation.clause_id)
    version = session.get(InstrumentVersion, clause.instrument_version_id)
    instrument = session.get(Instrument, version.instrument_id)
    maybe_record_onboarding_completion(session, instrument)

    return obligation


def correct_obligation(
    session: Session,
    *,
    obligation: Obligation,
    summary: str,
    obligation_type: str,
    fields: dict[str, Any],
    confidence: int,
) -> Obligation:
    """A correction to an *approved* obligation: closes the old row's
    valid_to and inserts a fresh, unapproved one on the same clause — a
    new version, never a mutation (CONVENTIONS.md rule #2)."""
    now = datetime.now(UTC)
    obligation.valid_to = now
    session.flush()

    corrected = Obligation(
        clause_id=obligation.clause_id,
        summary=summary,
        obligation_type=obligation_type,
        fields=fields,
        confidence=confidence,
        extracted_by=f"correction of {obligation.id}",
        approved=False,
        valid_from=now,
    )
    session.add(corrected)
    session.flush()
    return corrected


# --- Predicates: draft, edit, approve ---------------------------------------


def draft_predicate(
    session: Session,
    *,
    obligation: Obligation,
    available_fields: list[dict[str, Any]],
    provider: PredicateAssistProvider,
) -> Predicate:
    who = obligation.fields["who"]
    threshold = obligation.fields["threshold"]
    drafted = provider.draft(
        obligation_summary=obligation.summary,
        who_value=who["value"],
        who_clause_ref=who["clause_ref"],
        threshold_value=threshold["value"],
        threshold_clause_ref=threshold["clause_ref"],
        available_fields=available_fields,
    )
    predicate = Predicate(
        obligation_id=obligation.id,
        predicate_key=drafted.predicate_key,
        expression=drafted.expression,
        status=PredicateStatus.DRAFT,
        drafted_by_ai=True,
        valid_from=datetime.now(UTC),
    )
    session.add(predicate)
    session.flush()
    return predicate


def create_predicate(
    session: Session, *, obligation: Obligation, predicate_key: str, expression: dict[str, Any]
) -> Predicate:
    """A hand-written predicate, skipping P-PREDICATE-ASSIST entirely —
    still starts as DRAFT, same approval gate as an AI-drafted one."""
    validate_expression(expression)
    predicate = Predicate(
        obligation_id=obligation.id,
        predicate_key=predicate_key,
        expression=expression,
        status=PredicateStatus.DRAFT,
        drafted_by_ai=False,
        valid_from=datetime.now(UTC),
    )
    session.add(predicate)
    session.flush()
    return predicate


def update_predicate(
    session: Session, *, predicate: Predicate, expression: dict[str, Any]
) -> Predicate:
    if predicate.status is PredicateStatus.APPROVED:
        raise PredicateLockedError(f"Predicate {predicate.id} is already approved")
    validate_expression(expression)
    predicate.expression = expression
    session.flush()
    return predicate


def approve_predicate(
    session: Session, *, predicate: Predicate, approved_by_user_id: uuid.UUID
) -> Predicate:
    if predicate.status is PredicateStatus.APPROVED:
        raise PredicateLockedError(f"Predicate {predicate.id} is already approved")
    validate_expression(predicate.expression)
    predicate.status = PredicateStatus.APPROVED
    predicate.approved_by_user_id = approved_by_user_id
    predicate.approved_at = datetime.now(UTC)
    session.flush()
    return predicate


# --- Cost templates: always append-only -------------------------------------


def attach_cost_template(
    session: Session,
    *,
    obligation: Obligation,
    name: str,
    drivers: list[dict[str, Any]],
    formula: dict[str, Any],
    currency: str,
    source_basis: str,
    maturity_tier: str,
    first_obligation_date: date | None = None,
    transition_months: int = 0,
) -> CostTemplate:
    now = datetime.now(UTC)
    current = session.execute(
        select(CostTemplate).where(
            CostTemplate.obligation_id == obligation.id, CostTemplate.valid_to.is_(None)
        )
    ).scalar_one_or_none()
    if current is not None:
        current.valid_to = now
        session.flush()

    template = CostTemplate(
        obligation_id=obligation.id,
        name=name,
        drivers=drivers,
        formula=formula,
        currency=currency,
        source_basis=source_basis,
        maturity_tier=maturity_tier,
        first_obligation_date=first_obligation_date,
        transition_months=transition_months,
        valid_from=now,
    )
    session.add(template)
    session.flush()
    return template

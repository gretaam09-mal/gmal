"""F4 orchestration: the DB-touching half of the applicability engine.
engine/predicates does the actual tri-state evaluation, engine/impact the
cost quantification, engine/rationale the written explanation — all pure.
This module's only job is fetching facts and reference data, calling
those pure functions in a loop, and persisting the result.

The approval gate lives entirely in the query in `_approved_predicates`:
a predicate never reaches this loop unless status=APPROVED *and* its
obligation is approved=True — nothing unapproved can ever produce an
AnalysisItem (F3 success criterion: nothing reaches a client unless
approved=true).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    Analysis,
    AnalysisItem,
    Clause,
    CostTemplate,
    Instrument,
    InstrumentVersion,
    Memo,
    MemoVersion,
    Obligation,
    Predicate,
    ProfileField,
)
from db.models.enums import AnalysisStatus, PredicateStatus
from engine.impact import compute_impact, impact_band
from engine.predicates import PredicateOutcome, evaluate_predicate
from engine.rationale import build_rationale

ENGINE_VERSION = "1"


class _PredicateContext(NamedTuple):
    predicate: Predicate
    obligation: Obligation
    clause: Clause
    instrument: Instrument


def _approved_predicate_contexts(session: Session) -> list[_PredicateContext]:
    """Every predicate F4 is allowed to evaluate: APPROVED, whose
    obligation is approved=True. This one query is the entire enforcement
    of "nothing reaches a client unless approved=true" — see module
    docstring."""
    rows = session.execute(
        select(Predicate, Obligation, Clause, Instrument)
        .join(Obligation, Obligation.id == Predicate.obligation_id)
        .join(Clause, Clause.id == Obligation.clause_id)
        .join(InstrumentVersion, InstrumentVersion.id == Clause.instrument_version_id)
        .join(Instrument, Instrument.id == InstrumentVersion.instrument_id)
        .where(
            Predicate.status == PredicateStatus.APPROVED,
            Predicate.valid_to.is_(None),
            Obligation.approved.is_(True),
            Obligation.valid_to.is_(None),
        )
    ).all()
    return [_PredicateContext(*row) for row in rows]


def build_facts(session: Session, entity_profile_id: uuid.UUID) -> dict[str, Any]:
    fields = session.execute(
        select(ProfileField).where(ProfileField.entity_profile_id == entity_profile_id)
    ).scalars()
    return {f.field_key: f.field_value for f in fields}


def run_analysis(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    entity_profile_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
) -> Analysis:
    """Evaluates every APPROVED predicate against one profile version and
    persists one AnalysisItem per predicate. See F4's 60-second success
    criterion — this loop is pure-function calls over data already in
    memory, no I/O per predicate, so it stays well inside that bound even
    for a large predicate set (see tests/unit/test_analyses_performance.py).
    """
    analysis = Analysis(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        entity_profile_id=entity_profile_id,
        status=AnalysisStatus.RUNNING,
        created_by_user_id=created_by_user_id,
    )
    session.add(analysis)
    session.flush()

    facts = build_facts(session, entity_profile_id)
    contexts = _approved_predicate_contexts(session)
    now = datetime.now(UTC)

    for predicate, obligation, _clause, _instrument in contexts:
        evaluation = evaluate_predicate(predicate.expression, facts)
        clause_refs = tuple(
            sorted({field["clause_ref"] for field in obligation.fields.values()})
        )
        rationale = build_rationale(
            obligation_summary=obligation.summary,
            expression=predicate.expression,
            facts=facts,
            evaluation=evaluation,
            clause_refs=clause_refs,
        )

        amount = None
        currency = "GBP"
        if evaluation.outcome is PredicateOutcome.BINDS:
            cost_template = session.execute(
                select(CostTemplate).where(
                    CostTemplate.obligation_id == obligation.id, CostTemplate.valid_to.is_(None)
                )
            ).scalar_one_or_none()
            if cost_template is not None:
                impact = compute_impact(
                    cost_template.formula, facts, currency=cost_template.currency
                )
                amount = impact.amount
                currency = impact.currency

        session.add(
            AnalysisItem(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                analysis_id=analysis.id,
                predicate_id=predicate.id,
                outcome=evaluation.outcome,
                missing_field_keys=list(evaluation.missing_field_keys),
                rationale=rationale,
                amount=amount,
                currency=currency,
                engine_version=ENGINE_VERSION,
                computed_at=now,
            )
        )

    analysis.status = AnalysisStatus.COMPLETE
    session.flush()
    return analysis


class AnalysisItemView(NamedTuple):
    """The read-model for one Exposure List row — an AnalysisItem plus
    the reference-data context it doesn't itself store (instrument
    title, obligation summary/confidence, clause refs) and the one piece
    of tenant data it does need a fresh lookup for (memo status)."""

    item: AnalysisItem
    instrument_title: str
    obligation_summary: str
    obligation_confidence: int
    clause_refs: tuple[str, ...]
    first_obligation_date: str | None
    impact_band: str
    memo_status: str


def _try_parse_date(value: str) -> str | None:
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except (ValueError, TypeError):
        return None


def get_memo_status(session: Session, analysis_id: uuid.UUID) -> str:
    latest = session.execute(
        select(MemoVersion.status)
        .join(Memo, Memo.id == MemoVersion.memo_id)
        .where(Memo.analysis_id == analysis_id)
        .order_by(MemoVersion.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    return latest.value if latest is not None else "not_started"


def list_analysis_item_views(session: Session, analysis_id: uuid.UUID) -> list[AnalysisItemView]:
    memo_status = get_memo_status(session, analysis_id)
    rows = session.execute(
        select(AnalysisItem, Obligation, Instrument)
        .join(Predicate, Predicate.id == AnalysisItem.predicate_id)
        .join(Obligation, Obligation.id == Predicate.obligation_id)
        .join(Clause, Clause.id == Obligation.clause_id)
        .join(InstrumentVersion, InstrumentVersion.id == Clause.instrument_version_id)
        .join(Instrument, Instrument.id == InstrumentVersion.instrument_id)
        .where(AnalysisItem.analysis_id == analysis_id)
    ).all()

    views = []
    for item, obligation, instrument in rows:
        clause_refs = tuple(sorted({f["clause_ref"] for f in obligation.fields.values()}))
        when_value = obligation.fields.get("when", {}).get("value")
        views.append(
            AnalysisItemView(
                item=item,
                instrument_title=instrument.title,
                obligation_summary=obligation.summary,
                obligation_confidence=obligation.confidence,
                clause_refs=clause_refs,
                first_obligation_date=_try_parse_date(when_value) if when_value else None,
                impact_band=impact_band(item.amount),
                memo_status=memo_status,
            )
        )
    return views

"""F6 orchestration: the DB-touching half of the Impact Memo.

engine/impact and engine/confidence compute every number; services/
composition (P-COMPOSE) and services/diff_note (P-DIFF-NOTE) write the
narrative around them — this module's job is fetching an Analysis's
results, assembling the memo content and assumption register, and
persisting/overriding/approving memo versions. It enforces the state
machine (Draft -> In Review -> Approved) and CONVENTIONS.md rule 2 at
the service layer; the DB trigger (see migration a3f1c9d47b2e) is the
backstop that makes it a guarantee rather than a convention.

Overriding an assumption recomputes *cost*, not *applicability* — which
obligations bind (AnalysisItem.outcome) was already decided, once, by
engine/predicates at analysis time (see services/analyses.py) and is
never re-evaluated here. Only the figures downstream of a binding
obligation's cost template (driver facts, discount rate, FX rate,
scenario probabilities) are overridable and recomputed.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    Analysis,
    AnalysisItem,
    Assumption,
    Clause,
    CostTemplate,
    Instrument,
    InstrumentVersion,
    Memo,
    MemoVersion,
    Obligation,
    Predicate,
    Review,
)
from db.models.enums import AnalysisItemOutcome, MemoStatus, ReviewDecision
from engine.completeness.calculator import FieldState, compute_completeness
from engine.confidence import SCENARIO_SOURCE_SCORES, compute_confidence_grade
from engine.diff import Change, compute_assumption_diff
from engine.impact import (
    BASE_RATE_TABLES,
    RangeResult,
    ScenarioWeight,
    compute_range,
    compute_weighted_range,
    discount_to_present_value,
    phase_schedule,
)
from services.analyses import build_facts
from services.composition.context import MemoComposeContext, ObligationComposeInput
from services.composition.provider import CompositionProvider
from services.composition.schemas import ComposedMemoProse
from services.diff_note.provider import DiffNoteProvider
from services.diff_note.schemas import ComposedDiffNote
from services.entity_profile import get_profile_fields
from services.metrics import record_assumption_override, record_memo_approved, record_review_minutes
from services.scenarios import get_latest_scenario_weights

_MATURITY_RANK = {"rough": 0, "estimated": 1, "benchmarked": 2, "quoted": 3}


class MemoLockedError(Exception):
    """Raised when the caller tries to edit an approved memo version
    directly instead of creating a new one — see CONVENTIONS.md rule 2."""


class MemoStateError(Exception):
    """Raised on an invalid Draft -> In Review -> Approved transition."""


@dataclass(frozen=True)
class AssumptionSpec:
    key: str
    value: dict[str, Any]
    source: str
    note: str | None = None


class _ItemContext(NamedTuple):
    item: AnalysisItem
    predicate: Predicate
    obligation: Obligation
    instrument: Instrument
    clause_text: str
    clause_ref: str
    cost_template: CostTemplate | None


def _item_contexts(session: Session, analysis_id: uuid.UUID) -> list[_ItemContext]:
    rows = session.execute(
        select(AnalysisItem, Predicate, Obligation, Instrument, Clause, CostTemplate)
        .join(Predicate, Predicate.id == AnalysisItem.predicate_id)
        .join(Obligation, Obligation.id == Predicate.obligation_id)
        .join(Clause, Clause.id == Obligation.clause_id)
        .join(InstrumentVersion, InstrumentVersion.id == Clause.instrument_version_id)
        .join(Instrument, Instrument.id == InstrumentVersion.instrument_id)
        .outerjoin(
            CostTemplate,
            (CostTemplate.obligation_id == Obligation.id) & (CostTemplate.valid_to.is_(None)),
        )
        .where(AnalysisItem.analysis_id == analysis_id)
    ).all()
    return [
        _ItemContext(
            item=item,
            predicate=predicate,
            obligation=obligation,
            instrument=instrument,
            clause_text=clause.text,
            clause_ref=clause.clause_ref,
            cost_template=cost_template,
        )
        for item, predicate, obligation, instrument, clause, cost_template in rows
    ]


def _memo_version_assumptions(session: Session, memo_version_id: uuid.UUID) -> list[Assumption]:
    return list(
        session.execute(
            select(Assumption).where(Assumption.memo_version_id == memo_version_id)
        ).scalars()
    )


# --- Assumption register -----------------------------------------------------


def _build_assumption_specs(
    session: Session,
    analysis: Analysis,
    contexts: list[_ItemContext],
    facts: dict[str, Any],
) -> list[AssumptionSpec]:
    specs = [
        AssumptionSpec(
            key="discount_rate_pct",
            value={"value": str(analysis.discount_rate_pct)},
            source="analysis_setting",
        ),
        AssumptionSpec(
            key="fx_rate",
            value={"value": str(analysis.fx_rate)},
            source="analysis_setting",
        ),
    ]
    seen_drivers: set[str] = set()
    for ctx in contexts:
        if ctx.item.outcome is not AnalysisItemOutcome.BINDS or ctx.cost_template is None:
            continue
        predicate_id = str(ctx.predicate.id)
        for term in ctx.cost_template.formula.get("terms", []):
            driver_key = term["driver"]
            spec_key = f"driver:{predicate_id}:{driver_key}"
            if spec_key in seen_drivers or facts.get(driver_key) is None:
                continue
            seen_drivers.add(spec_key)
            specs.append(
                AssumptionSpec(
                    key=spec_key,
                    value={"value": str(facts[driver_key])},
                    source=f"profile_field:{driver_key}",
                )
            )
        if ctx.instrument.in_flight:
            recorded = get_latest_scenario_weights(session, ctx.predicate.id)
            if recorded:
                for name, record in recorded.items():
                    specs.append(
                        AssumptionSpec(
                            key=f"scenario:{predicate_id}:{name}",
                            value={
                                "probability": str(record.probability),
                                "magnitude_multiplier": str(record.magnitude_multiplier),
                            },
                            source=record.source,
                        )
                    )
            else:
                for name, probability in BASE_RATE_TABLES["default"].items():
                    specs.append(
                        AssumptionSpec(
                            key=f"scenario:{predicate_id}:{name}",
                            value={"probability": str(probability), "magnitude_multiplier": "1"},
                            source="base_rate_table",
                        )
                    )
    return specs


_DriverFacts = dict[str, dict[str, Decimal]]
_ScenarioWeights = dict[str, dict[str, tuple[Decimal, Decimal]]]


def _facts_and_scenarios_from_items(
    items: list[Any],
) -> tuple[Decimal, Decimal, _DriverFacts, _ScenarioWeights]:
    discount_rate_pct = Decimal("0")
    fx_rate = Decimal("1")
    driver_facts: _DriverFacts = {}
    scenario_weights: _ScenarioWeights = {}
    for item in items:
        if item.key == "discount_rate_pct":
            discount_rate_pct = Decimal(item.value["value"])
        elif item.key == "fx_rate":
            fx_rate = Decimal(item.value["value"])
        elif item.key.startswith("driver:"):
            _, predicate_id, driver_key = item.key.split(":", 2)
            driver_facts.setdefault(predicate_id, {})[driver_key] = Decimal(item.value["value"])
        elif item.key.startswith("scenario:"):
            _, predicate_id, scenario_name = item.key.split(":", 2)
            scenario_weights.setdefault(predicate_id, {})[scenario_name] = (
                Decimal(item.value["probability"]),
                Decimal(item.value.get("magnitude_multiplier", "1")),
            )
    return discount_rate_pct, fx_rate, driver_facts, scenario_weights


# --- Numeric content assembly -------------------------------------------------


def _compute_obligation_numbers(
    ctx: _ItemContext,
    *,
    driver_facts: dict[str, Decimal],
    scenario_weights: dict[str, tuple[Decimal, Decimal]] | None,
    discount_rate_pct: Decimal,
    fx_rate: Decimal,
    analysis_date,
) -> dict[str, Any] | None:
    if ctx.cost_template is None:
        return None
    point_range = compute_range(
        ctx.cost_template.formula, driver_facts, currency=ctx.cost_template.currency
    )
    if point_range.likely is None:
        return None
    if ctx.instrument.in_flight and scenario_weights:
        weights = tuple(
            ScenarioWeight(
                scenario=name,
                probability=probability,
                range=RangeResult(
                    best=point_range.best * multiplier,
                    likely=point_range.likely * multiplier,
                    worst=point_range.worst * multiplier,
                    currency=point_range.currency,
                ),
            )
            for name, (probability, multiplier) in scenario_weights.items()
        )
        final_range = compute_weighted_range(weights)
    else:
        final_range = point_range
    entries = phase_schedule(
        final_range.likely,
        first_obligation_date=ctx.cost_template.first_obligation_date,
        transition_months=ctx.cost_template.transition_months,
        analysis_date=analysis_date,
    )
    present_value = discount_to_present_value(
        [entry.amount for entry in entries], discount_rate_pct=discount_rate_pct, fx_rate=fx_rate
    )
    return {
        "impact_low": final_range.best,
        "impact_likely": final_range.likely,
        "impact_high": final_range.worst,
        "currency": final_range.currency,
        "phased_schedule": entries,
        "present_value": present_value,
    }


def _weakest_maturity_tier(contexts: list[_ItemContext]) -> str:
    tiers = [
        ctx.cost_template.maturity_tier
        for ctx in contexts
        if ctx.item.outcome is AnalysisItemOutcome.BINDS and ctx.cost_template is not None
    ]
    if not tiers:
        return "rough"
    return min(tiers, key=lambda tier: _MATURITY_RANK.get(tier, 0))


def _average_extraction_confidence(contexts: list[_ItemContext]) -> float:
    scores = [
        ctx.obligation.confidence
        for ctx in contexts
        if ctx.item.outcome is AnalysisItemOutcome.BINDS
    ]
    return sum(scores) / len(scores) if scores else 0.0


def _scenario_source_quality(contexts: list[_ItemContext], assumptions: list[Any]) -> str:
    in_flight_ids = {
        str(ctx.predicate.id)
        for ctx in contexts
        if ctx.item.outcome is AnalysisItemOutcome.BINDS and ctx.instrument.in_flight
    }
    if not in_flight_ids:
        return "not_applicable"
    sources = {
        a.source
        for a in assumptions
        if a.key.startswith("scenario:") and a.key.split(":", 2)[1] in in_flight_ids
    }
    if not sources:
        return "unvalidated"
    return sorted(sources, key=lambda source: SCENARIO_SOURCE_SCORES.get(source, Decimal("0")))[0]


def _build_numeric_content(
    session: Session,
    *,
    analysis: Analysis,
    contexts: list[_ItemContext],
    assumption_items: list[Any],
) -> dict[str, Any]:
    discount_rate_pct, fx_rate, driver_facts, scenario_weights = _facts_and_scenarios_from_items(
        assumption_items
    )
    analysis_date = analysis.created_at.date()

    obligations: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    headline_low = headline_likely = headline_high = Decimal("0")
    currency = analysis.base_currency

    for ctx in contexts:
        predicate_id = str(ctx.predicate.id)
        if ctx.item.outcome is not AnalysisItemOutcome.BINDS:
            excluded.append(
                {
                    "predicate_id": predicate_id,
                    "obligation_summary": ctx.obligation.summary,
                    "outcome": ctx.item.outcome.value,
                    "rationale": ctx.item.rationale,
                }
            )
            continue
        numbers = _compute_obligation_numbers(
            ctx,
            driver_facts=driver_facts.get(predicate_id, {}),
            scenario_weights=scenario_weights.get(predicate_id),
            discount_rate_pct=discount_rate_pct,
            fx_rate=fx_rate,
            analysis_date=analysis_date,
        )
        if numbers is None:
            continue
        headline_low += numbers["impact_low"]
        headline_likely += numbers["impact_likely"]
        headline_high += numbers["impact_high"]
        currency = numbers["currency"]
        obligations.append(
            {
                "predicate_id": predicate_id,
                "obligation_summary": ctx.obligation.summary,
                "clause_refs": [ctx.clause_ref],
                "rationale": ctx.item.rationale,
                "impact_low": str(numbers["impact_low"]),
                "impact_likely": str(numbers["impact_likely"]),
                "impact_high": str(numbers["impact_high"]),
                "currency": numbers["currency"],
                "phased_schedule": [
                    {"period": entry.period, "amount": str(entry.amount)}
                    for entry in numbers["phased_schedule"]
                ],
                "present_value": str(numbers["present_value"]),
                "what_it_requires": "",
                "why_it_applies": "",
            }
        )

    profile_fields = get_profile_fields(session, analysis.entity_profile_id)
    field_states = {f.field_key: FieldState(f.field_key, f.source.value) for f in profile_fields}
    completeness = compute_completeness(field_states)

    confidence = compute_confidence_grade(
        profile_completeness_score=completeness.overall_score,
        template_maturity_tier=_weakest_maturity_tier(contexts),
        extraction_confidence_pct=_average_extraction_confidence(contexts),
        scenario_source_quality=_scenario_source_quality(contexts, assumption_items),
    )

    return {
        "headline": {
            "low": str(headline_low),
            "likely": str(headline_likely),
            "high": str(headline_high),
            "currency": currency,
        },
        "confidence_grade": confidence.grade,
        "confidence_score": str(confidence.score),
        "obligations": obligations,
        "excluded": excluded,
        "headline_summary": "",
        "excluded_summary": "",
    }


def _compose_context(contexts: list[_ItemContext], content: dict[str, Any]) -> MemoComposeContext:
    clause_text_by_id = {str(ctx.predicate.id): ctx.clause_text for ctx in contexts}
    headline = content["headline"]
    binding = tuple(
        ObligationComposeInput(
            predicate_id=o["predicate_id"],
            obligation_summary=o["obligation_summary"],
            outcome="binds",
            rationale=o["rationale"],
            clause_texts=(clause_text_by_id.get(o["predicate_id"], ""),),
            clause_refs=tuple(o["clause_refs"]),
            impact_low=Decimal(o["impact_low"]),
            impact_likely=Decimal(o["impact_likely"]),
            impact_high=Decimal(o["impact_high"]),
            currency=o["currency"],
        )
        for o in content["obligations"]
    )
    excluded = tuple(
        ObligationComposeInput(
            predicate_id=e["predicate_id"],
            obligation_summary=e["obligation_summary"],
            outcome=e["outcome"],
            rationale=e["rationale"],
            clause_texts=(),
            clause_refs=(),
            impact_low=None,
            impact_likely=None,
            impact_high=None,
            currency=headline["currency"],
        )
        for e in content["excluded"]
    )
    return MemoComposeContext(
        headline_low=Decimal(headline["low"]),
        headline_likely=Decimal(headline["likely"]),
        headline_high=Decimal(headline["high"]),
        currency=headline["currency"],
        confidence_grade=content["confidence_grade"],
        binding_obligations=binding,
        excluded_obligations=excluded,
    )


def _merge_prose(content: dict[str, Any], prose: ComposedMemoProse) -> dict[str, Any]:
    content = dict(content)
    content["headline_summary"] = prose.headline_summary
    content["excluded_summary"] = prose.excluded_summary
    prose_by_id = {o.predicate_id: o for o in prose.obligations}
    content["obligations"] = [
        {
            **o,
            "what_it_requires": prose_by_id[o["predicate_id"]].what_it_requires,
            "why_it_applies": prose_by_id[o["predicate_id"]].why_it_applies,
        }
        if o["predicate_id"] in prose_by_id
        else o
        for o in content["obligations"]
    ]
    return content


def _carry_forward_prose(
    new_content: dict[str, Any], old_content: dict[str, Any]
) -> dict[str, Any]:
    new_content = dict(new_content)
    new_content["headline_summary"] = old_content.get("headline_summary", "")
    new_content["excluded_summary"] = old_content.get("excluded_summary", "")
    old_by_id = {o["predicate_id"]: o for o in old_content.get("obligations", [])}
    merged = []
    for o in new_content["obligations"]:
        old_o = old_by_id.get(o["predicate_id"])
        entry = dict(o)
        if old_o:
            entry["what_it_requires"] = old_o.get("what_it_requires", "")
            entry["why_it_applies"] = old_o.get("why_it_applies", "")
        merged.append(entry)
    new_content["obligations"] = merged
    return new_content


def _numeric_from_value(value: dict[str, Any]) -> Decimal | None:
    raw = value.get("value")
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def _numeric_snapshot(content: dict[str, Any]) -> dict[str, Decimal]:
    snapshot = {
        "headline_low": Decimal(content["headline"]["low"]),
        "headline_likely": Decimal(content["headline"]["likely"]),
        "headline_high": Decimal(content["headline"]["high"]),
    }
    for o in content["obligations"]:
        snapshot[f"{o['predicate_id']}:impact_likely"] = Decimal(o["impact_likely"])
        snapshot[f"{o['predicate_id']}:present_value"] = Decimal(o["present_value"])
    return snapshot


# --- Public orchestration -----------------------------------------------------


def create_memo_from_analysis(
    session: Session,
    *,
    analysis: Analysis,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    title: str,
    created_by_user_id: uuid.UUID,
    composition_provider: CompositionProvider,
) -> Memo:
    contexts = _item_contexts(session, analysis.id)
    facts = build_facts(session, analysis.entity_profile_id)
    specs = _build_assumption_specs(session, analysis, contexts, facts)

    memo = Memo(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        analysis_id=analysis.id,
        title=title,
        created_by_user_id=created_by_user_id,
    )
    session.add(memo)
    session.flush()

    numeric_content = _build_numeric_content(
        session, analysis=analysis, contexts=contexts, assumption_items=specs
    )
    compose_context = _compose_context(contexts, numeric_content)
    prose = composition_provider.compose(compose_context)
    content = _merge_prose(numeric_content, prose)

    memo_version = MemoVersion(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        memo_id=memo.id,
        version=1,
        content=content,
        status=MemoStatus.DRAFT,
        confidence_grade=content["confidence_grade"],
        created_by_user_id=created_by_user_id,
    )
    session.add(memo_version)
    session.flush()

    for spec in specs:
        session.add(
            Assumption(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                memo_version_id=memo_version.id,
                key=spec.key,
                value=spec.value,
                source=spec.source,
                note=spec.note,
            )
        )
    session.flush()
    return memo


def override_assumption_and_recompute(
    session: Session,
    *,
    memo_version: MemoVersion,
    assumption: Assumption,
    new_value: dict[str, Any],
    note: str | None,
    diff_note_provider: DiffNoteProvider,
) -> tuple[MemoVersion, ComposedDiffNote, tuple[Change, ...]]:
    if memo_version.status == MemoStatus.APPROVED:
        raise MemoLockedError("Cannot override an assumption on an approved memo version")

    memo = session.get(Memo, memo_version.memo_id)
    analysis = session.get(Analysis, memo.analysis_id)
    contexts = _item_contexts(session, analysis.id)

    old_snapshot = _numeric_snapshot(memo_version.content)
    old_assumption_numeric = _numeric_from_value(assumption.value)
    if old_assumption_numeric is not None:
        old_snapshot[f"assumption:{assumption.key}"] = old_assumption_numeric

    assumption.value = new_value
    assumption.note = note
    session.flush()

    assumption_items = _memo_version_assumptions(session, memo_version.id)
    new_numeric_content = _build_numeric_content(
        session, analysis=analysis, contexts=contexts, assumption_items=assumption_items
    )
    new_content = _carry_forward_prose(new_numeric_content, memo_version.content)

    memo_version.content = new_content
    memo_version.confidence_grade = new_content["confidence_grade"]
    session.flush()

    new_snapshot = _numeric_snapshot(new_content)
    new_assumption_numeric = _numeric_from_value(new_value)
    if new_assumption_numeric is not None:
        new_snapshot[f"assumption:{assumption.key}"] = new_assumption_numeric
    changes = compute_assumption_diff(old_snapshot, new_snapshot)
    diff_note = diff_note_provider.summarise(changes)
    record_assumption_override(
        session,
        tenant_id=memo_version.tenant_id,
        workspace_id=memo_version.workspace_id,
        memo_version_id=memo_version.id,
        assumption_key=assumption.key,
    )
    return memo_version, diff_note, changes


def submit_for_review(memo_version: MemoVersion) -> None:
    if memo_version.status != MemoStatus.DRAFT:
        raise MemoStateError(f"Cannot submit a memo version in status {memo_version.status.value}")
    memo_version.status = MemoStatus.IN_REVIEW
    memo_version.submitted_at = datetime.now(UTC)


def approve_memo(
    session: Session,
    *,
    memo_version: MemoVersion,
    approved_by_user_id: uuid.UUID,
    panel_firm: str | None = None,
) -> None:
    if memo_version.status != MemoStatus.IN_REVIEW:
        raise MemoStateError(
            f"Cannot approve a memo version in status {memo_version.status.value}"
        )
    memo_version.status = MemoStatus.APPROVED
    memo_version.approved_at = datetime.now(UTC)
    memo_version.approved_by_user_id = approved_by_user_id
    session.add(
        Review(
            tenant_id=memo_version.tenant_id,
            workspace_id=memo_version.workspace_id,
            memo_version_id=memo_version.id,
            reviewer_user_id=approved_by_user_id,
            decision=ReviewDecision.APPROVED,
            panel_firm=panel_firm,
        )
    )
    session.flush()
    record_review_minutes(session, memo_version=memo_version, reviewer_user_id=approved_by_user_id)
    memo = session.get(Memo, memo_version.memo_id)
    record_memo_approved(session, memo_version=memo_version, memo_created_at=memo.created_at)


def create_new_version_from_approved(
    session: Session,
    *,
    memo: Memo,
    base_version: MemoVersion,
    change_note: str,
    created_by_user_id: uuid.UUID,
) -> MemoVersion:
    """Approved memos are immutable — any later change is a new version,
    carrying the base version's content/assumptions forward with a
    change note, never a mutation of the one it supersedes."""
    if base_version.status != MemoStatus.APPROVED:
        raise MemoStateError("Can only branch a new version from an approved one")
    content = dict(base_version.content)
    content["change_note"] = change_note
    content["superseded_version"] = base_version.version
    new_version = MemoVersion(
        tenant_id=base_version.tenant_id,
        workspace_id=base_version.workspace_id,
        memo_id=memo.id,
        version=base_version.version + 1,
        content=content,
        status=MemoStatus.DRAFT,
        created_by_user_id=created_by_user_id,
    )
    session.add(new_version)
    session.flush()

    for existing in _memo_version_assumptions(session, base_version.id):
        session.add(
            Assumption(
                tenant_id=existing.tenant_id,
                workspace_id=existing.workspace_id,
                memo_version_id=new_version.id,
                key=existing.key,
                value=existing.value,
                source=existing.source,
                note=existing.note,
            )
        )
    session.flush()
    return new_version

"""F3 — the instrument-onboarding workbench. Staff-only (require_staff),
internal, and never linked from the client-facing UI — see
api/deps.py::require_staff and frontend/app/(admin).

instruments/clauses/obligations/predicates/cost_templates are shared
reference data, not tenant data (db/models/regulatory.py), so these
routes use get_raw_session directly rather than a workspace-scoped
session — there is no tenant to scope to.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import (
    get_extraction_provider,
    get_predicate_assist_provider,
    get_raw_session,
    require_staff,
)
from api.schemas import (
    ClauseOut,
    CostTemplateCreateRequest,
    CostTemplateOut,
    ExtractObligationRequest,
    InstrumentCreateRequest,
    InstrumentDetailOut,
    InstrumentOut,
    InstrumentVersionOut,
    ObligationCorrectRequest,
    ObligationOut,
    ObligationUpdateRequest,
    OnboardingMetricOut,
    PredicateCreateRequest,
    PredicateOut,
    PredicateTestResultOut,
    PredicateUpdateRequest,
)
from db.models import (
    Clause,
    CostTemplate,
    Instrument,
    InstrumentVersion,
    MetricsEvent,
    Obligation,
    Predicate,
    User,
)
from engine.completeness.catalog import FIELD_CATALOG
from engine.predicates.dsl import InvalidExpressionError
from services.extraction.provider import ExtractionError, ExtractionProvider
from services.instrument_onboarding import (
    ObligationLockedError,
    PredicateLockedError,
    approve_obligation,
    approve_predicate,
    attach_cost_template,
    correct_obligation,
    create_predicate,
    draft_predicate,
    extract_obligation,
    ingest_instrument,
    list_clauses,
    update_obligation,
    update_predicate,
)
from services.onboarding_metrics import ONBOARDING_COMPLETED_EVENT
from services.predicate_assist.provider import PredicateAssistError, PredicateAssistProvider
from services.predicate_testrunner import run_predicate_against_fixtures

router = APIRouter(prefix="/admin", tags=["admin-instrument-onboarding"])


def _instrument_detail(session: Session, instrument: Instrument) -> InstrumentDetailOut:
    versions = list(
        session.execute(
            select(InstrumentVersion).where(InstrumentVersion.instrument_id == instrument.id)
        ).scalars()
    )
    return InstrumentDetailOut(
        id=instrument.id,
        title=instrument.title,
        jurisdiction=instrument.jurisdiction,
        kind=instrument.kind,
        citation=instrument.citation,
        recorded_at=instrument.recorded_at,
        versions=[
            InstrumentVersionOut(
                id=v.id,
                instrument_id=v.instrument_id,
                version_label=v.version_label,
                source_url=v.source_url,
                content_hash=v.content_hash,
                clauses=[ClauseOut.model_validate(c) for c in list_clauses(session, v.id)],
            )
            for v in versions
        ],
    )


@router.post(
    "/instruments", response_model=InstrumentDetailOut, status_code=status.HTTP_201_CREATED
)
async def create_instrument(
    body: InstrumentCreateRequest,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> InstrumentDetailOut:
    version = ingest_instrument(
        session,
        title=body.title,
        jurisdiction=body.jurisdiction,
        kind=body.kind,
        citation=body.citation,
        version_label=body.version_label,
        source_url=body.source_url,
        raw_text=body.raw_text,
        in_flight=body.in_flight,
    )
    session.commit()
    instrument = session.get(Instrument, version.instrument_id)
    return _instrument_detail(session, instrument)


@router.get("/instruments", response_model=list[InstrumentOut])
async def list_instruments(
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> list[Instrument]:
    return list(
        session.execute(select(Instrument).order_by(Instrument.recorded_at.desc())).scalars()
    )


def _get_instrument_or_404(session: Session, instrument_id: uuid.UUID) -> Instrument:
    instrument = session.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instrument not found")
    return instrument


@router.get("/instruments/{instrument_id}", response_model=InstrumentDetailOut)
async def get_instrument(
    instrument_id: uuid.UUID,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> InstrumentDetailOut:
    instrument = _get_instrument_or_404(session, instrument_id)
    return _instrument_detail(session, instrument)


@router.get("/instruments/{instrument_id}/obligations", response_model=list[ObligationOut])
async def list_instrument_obligations(
    instrument_id: uuid.UUID,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> list[Obligation]:
    _get_instrument_or_404(session, instrument_id)
    return list(
        session.execute(
            select(Obligation)
            .join(Clause, Clause.id == Obligation.clause_id)
            .join(InstrumentVersion, InstrumentVersion.id == Clause.instrument_version_id)
            .where(
                InstrumentVersion.instrument_id == instrument_id,
                Obligation.valid_to.is_(None),
            )
            .order_by(Clause.ordinal)
        ).scalars()
    )


def _get_clause_or_404(session: Session, clause_id: uuid.UUID) -> Clause:
    clause = session.get(Clause, clause_id)
    if clause is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clause not found")
    return clause


@router.post(
    "/clauses/{clause_id}/obligations/extract",
    response_model=ObligationOut,
    status_code=status.HTTP_201_CREATED,
)
async def extract_clause_obligation(
    clause_id: uuid.UUID,
    body: ExtractObligationRequest,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
    provider: ExtractionProvider = Depends(get_extraction_provider),
) -> Obligation:
    """Runs P-EXTRACT over one clause. The result is persisted immediately
    but with approved=False — nothing here is client-visible until a
    human reviews it (see approve_obligation)."""
    clause = _get_clause_or_404(session, clause_id)
    try:
        obligation = extract_obligation(
            session, clause=clause, instrument_title=body.instrument_title, provider=provider
        )
    except ExtractionError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    session.commit()
    return obligation


def _get_obligation_or_404(session: Session, obligation_id: uuid.UUID) -> Obligation:
    obligation = session.get(Obligation, obligation_id)
    if obligation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Obligation not found")
    return obligation


@router.patch("/obligations/{obligation_id}", response_model=ObligationOut)
async def patch_obligation(
    obligation_id: uuid.UUID,
    body: ObligationUpdateRequest,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> Obligation:
    obligation = _get_obligation_or_404(session, obligation_id)
    try:
        update_obligation(
            session,
            obligation=obligation,
            summary=body.summary,
            obligation_type=body.obligation_type,
            fields={k: v.model_dump() for k, v in body.fields.items()} if body.fields else None,
            confidence=body.confidence,
        )
    except ObligationLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.commit()
    return obligation


@router.post("/obligations/{obligation_id}/approve", response_model=ObligationOut)
async def approve_obligation_route(
    obligation_id: uuid.UUID,
    staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> Obligation:
    obligation = _get_obligation_or_404(session, obligation_id)
    try:
        approve_obligation(session, obligation=obligation, approved_by_user_id=staff.id)
    except ObligationLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.commit()
    return obligation


@router.post("/obligations/{obligation_id}/correct", response_model=ObligationOut)
async def correct_obligation_route(
    obligation_id: uuid.UUID,
    body: ObligationCorrectRequest,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> Obligation:
    obligation = _get_obligation_or_404(session, obligation_id)
    corrected = correct_obligation(
        session,
        obligation=obligation,
        summary=body.summary,
        obligation_type=body.obligation_type,
        fields={k: v.model_dump() for k, v in body.fields.items()},
        confidence=body.confidence,
    )
    session.commit()
    return corrected


# --- Predicates --------------------------------------------------------------


@router.post(
    "/obligations/{obligation_id}/predicates/draft",
    response_model=PredicateOut,
    status_code=status.HTTP_201_CREATED,
)
async def draft_obligation_predicate(
    obligation_id: uuid.UUID,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
    provider: PredicateAssistProvider = Depends(get_predicate_assist_provider),
) -> Predicate:
    """Runs P-PREDICATE-ASSIST. Always persisted as status=DRAFT — see
    services/instrument_onboarding.py::draft_predicate; nothing in this
    call path can produce an APPROVED predicate."""
    obligation = _get_obligation_or_404(session, obligation_id)
    available_fields = [
        {"key": f.key, "label": f.label, "section": f.section} for f in FIELD_CATALOG
    ]
    try:
        predicate = draft_predicate(
            session, obligation=obligation, available_fields=available_fields, provider=provider
        )
    except PredicateAssistError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    session.commit()
    return predicate


@router.post(
    "/obligations/{obligation_id}/predicates",
    response_model=PredicateOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_predicate(
    obligation_id: uuid.UUID,
    body: PredicateCreateRequest,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> Predicate:
    obligation = _get_obligation_or_404(session, obligation_id)
    try:
        predicate = create_predicate(
            session,
            obligation=obligation,
            predicate_key=body.predicate_key,
            expression=body.expression,
        )
    except InvalidExpressionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    session.commit()
    return predicate


@router.get("/obligations/{obligation_id}/predicates", response_model=list[PredicateOut])
async def list_obligation_predicates(
    obligation_id: uuid.UUID,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> list[Predicate]:
    _get_obligation_or_404(session, obligation_id)
    return list(
        session.execute(
            select(Predicate)
            .where(Predicate.obligation_id == obligation_id, Predicate.valid_to.is_(None))
            .order_by(Predicate.recorded_at)
        ).scalars()
    )


def _get_predicate_or_404(session: Session, predicate_id: uuid.UUID) -> Predicate:
    predicate = session.get(Predicate, predicate_id)
    if predicate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Predicate not found")
    return predicate


@router.patch("/predicates/{predicate_id}", response_model=PredicateOut)
async def patch_predicate(
    predicate_id: uuid.UUID,
    body: PredicateUpdateRequest,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> Predicate:
    predicate = _get_predicate_or_404(session, predicate_id)
    try:
        update_predicate(session, predicate=predicate, expression=body.expression)
    except PredicateLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except InvalidExpressionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    session.commit()
    return predicate


@router.post("/predicates/{predicate_id}/test", response_model=list[PredicateTestResultOut])
async def test_predicate(
    predicate_id: uuid.UUID,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> list[PredicateTestResultOut]:
    """Runs the predicate's current expression against every fixture
    company profile in data/fixtures/company_profiles/ — lets a reviewer
    sanity-check a draft (or an already-approved rule) before/after
    approving it."""
    predicate = _get_predicate_or_404(session, predicate_id)
    try:
        results = run_predicate_against_fixtures(predicate.expression)
    except InvalidExpressionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return [
        PredicateTestResultOut(
            profile_name=r.profile_name,
            outcome=r.outcome.value,
            missing_field_keys=r.missing_field_keys,
        )
        for r in results
    ]


@router.post("/predicates/{predicate_id}/approve", response_model=PredicateOut)
async def approve_predicate_route(
    predicate_id: uuid.UUID,
    staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> Predicate:
    predicate = _get_predicate_or_404(session, predicate_id)
    try:
        approve_predicate(session, predicate=predicate, approved_by_user_id=staff.id)
    except PredicateLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.commit()
    return predicate


# --- Cost templates ------------------------------------------------------------


@router.post(
    "/obligations/{obligation_id}/cost-template",
    response_model=CostTemplateOut,
    status_code=status.HTTP_201_CREATED,
)
async def attach_obligation_cost_template(
    obligation_id: uuid.UUID,
    body: CostTemplateCreateRequest,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> CostTemplate:
    obligation = _get_obligation_or_404(session, obligation_id)
    template = attach_cost_template(
        session,
        obligation=obligation,
        name=body.name,
        drivers=body.drivers,
        formula=body.formula,
        currency=body.currency,
        source_basis=body.source_basis,
        maturity_tier=body.maturity_tier,
        first_obligation_date=body.first_obligation_date,
        transition_months=body.transition_months,
    )
    session.commit()
    return template


@router.get("/obligations/{obligation_id}/cost-template", response_model=CostTemplateOut | None)
async def get_obligation_cost_template(
    obligation_id: uuid.UUID,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
):
    _get_obligation_or_404(session, obligation_id)
    return session.execute(
        select(CostTemplate).where(
            CostTemplate.obligation_id == obligation_id, CostTemplate.valid_to.is_(None)
        )
    ).scalar_one_or_none()


# --- Board metric: onboarding hours -------------------------------------------


@router.get("/metrics/onboarding", response_model=list[OnboardingMetricOut])
async def list_onboarding_metrics(
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
):
    events = session.execute(
        select(MetricsEvent)
        .where(MetricsEvent.event_name == ONBOARDING_COMPLETED_EVENT)
        .order_by(MetricsEvent.created_at.desc())
    ).scalars()
    return [
        OnboardingMetricOut(
            instrument_id=e.properties["instrument_id"],
            instrument_title=e.properties["instrument_title"],
            onboarding_hours=e.properties["onboarding_hours"],
            started_at=e.properties["started_at"],
            completed_at=e.properties["completed_at"],
        )
        for e in events
    ]

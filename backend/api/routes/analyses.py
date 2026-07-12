"""F4 — the applicability engine's HTTP surface. Workspace-scoped (not the
literal `POST /analyses` named in the spec) to satisfy CONVENTIONS.md
rule #3: every other tenant-scoped route in this codebase is prefixed
`/workspaces/{workspace_id}/...` so tenancy is enforced the same way
everywhere — see api/routes/profiles.py for the identical shape.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_workspace_db, require_role
from api.schemas import AnalysisCreateRequest, AnalysisItemOut, AnalysisOut, PhaseEntryOut
from db.models import Analysis, Membership, Role, User
from services.analyses import list_analysis_item_views, run_analysis
from services.audit import record_audit_event
from services.entity_profile import get_current_profile

router = APIRouter(tags=["analyses"])

_ANY_ROLE = (Role.OWNER, Role.ANALYST, Role.APPROVER, Role.VIEWER)


def _to_out(session: Session, analysis: Analysis) -> AnalysisOut:
    views = list_analysis_item_views(session, analysis.id)
    return AnalysisOut(
        id=analysis.id,
        workspace_id=analysis.workspace_id,
        entity_profile_id=analysis.entity_profile_id,
        status=analysis.status.value,
        discount_rate_pct=float(analysis.discount_rate_pct),
        fx_rate=float(analysis.fx_rate),
        base_currency=analysis.base_currency,
        created_at=analysis.created_at,
        items=[
            AnalysisItemOut(
                id=v.item.id,
                predicate_id=v.item.predicate_id,
                instrument_title=v.instrument_title,
                obligation_summary=v.obligation_summary,
                outcome=v.item.outcome.value,
                missing_field_keys=tuple(v.item.missing_field_keys),
                rationale=v.item.rationale,
                clause_refs=v.clause_refs,
                amount=float(v.item.amount) if v.item.amount is not None else None,
                impact_low=float(v.item.impact_low) if v.item.impact_low is not None else None,
                impact_high=float(v.item.impact_high) if v.item.impact_high is not None else None,
                present_value=(
                    float(v.item.present_value) if v.item.present_value is not None else None
                ),
                phased_schedule=[
                    PhaseEntryOut(period=entry["period"], amount=float(entry["amount"]))
                    for entry in v.item.phased_schedule
                ],
                currency=v.item.currency,
                impact_band=v.impact_band,
                confidence=v.obligation_confidence,
                first_obligation_date=v.first_obligation_date,
                memo_status=v.memo_status,
                engine_version=v.item.engine_version,
                computed_at=v.item.computed_at,
            )
            for v in views
        ],
    )


@router.post(
    "/workspaces/{workspace_id}/analyses",
    response_model=AnalysisOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_analysis(
    body: AnalysisCreateRequest,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(Role.OWNER, Role.ANALYST)),
    session: Session = Depends(get_workspace_db),
) -> AnalysisOut:
    """Evaluates every APPROVED predicate against a profile version (the
    workspace's current one by default) — see services/analyses.py for
    the approval-gate query this can never bypass."""
    entity_profile_id = body.entity_profile_id
    if entity_profile_id is None:
        profile = get_current_profile(session, membership.workspace_id)
        if profile is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "This assessment has no entity profile yet"
            )
        entity_profile_id = profile.id

    analysis = run_analysis(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        entity_profile_id=entity_profile_id,
        created_by_user_id=current_user.id,
        discount_rate_pct=Decimal(str(body.discount_rate_pct)),
        fx_rate=Decimal(str(body.fx_rate)),
        base_currency=body.base_currency,
    )
    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="analysis.completed",
        entity_type="analysis",
        entity_id=analysis.id,
        payload={"entity_profile_id": str(entity_profile_id)},
    )
    session.commit()
    return _to_out(session, analysis)


@router.get("/workspaces/{workspace_id}/analyses/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(
    analysis_id: uuid.UUID,
    membership: Membership = Depends(require_role(*_ANY_ROLE)),
    session: Session = Depends(get_workspace_db),
) -> AnalysisOut:
    analysis = session.get(Analysis, analysis_id)
    if analysis is None or analysis.workspace_id != membership.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    return _to_out(session, analysis)


@router.get("/workspaces/{workspace_id}/analyses", response_model=list[AnalysisOut])
async def list_analyses(
    membership: Membership = Depends(require_role(*_ANY_ROLE)),
    session: Session = Depends(get_workspace_db),
) -> list[AnalysisOut]:
    analyses = session.execute(
        select(Analysis)
        .where(Analysis.workspace_id == membership.workspace_id)
        .order_by(Analysis.created_at.desc())
    ).scalars()
    return [_to_out(session, a) for a in analyses]

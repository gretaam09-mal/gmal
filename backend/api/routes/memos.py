"""F6 — the Impact Memo's HTTP surface. Workspace-scoped, same shape as
api/routes/analyses.py and api/routes/profiles.py, so tenancy is
enforced identically everywhere (CONVENTIONS.md rule #3).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import (
    get_composition_provider,
    get_current_user,
    get_diff_note_provider,
    get_workspace_db,
    require_role,
)
from api.schemas import (
    ApproveMemoRequest,
    AssumptionOut,
    AssumptionOverrideRequest,
    AssumptionOverrideResponse,
    ChangeOut,
    MemoCreateRequest,
    MemoOut,
    MemoVersionOut,
    NewVersionRequest,
    ReviewOut,
    ReviewQueueEntryOut,
    UsedInIcRequest,
)
from db.models import (
    Analysis,
    Assumption,
    Membership,
    Memo,
    MemoInputChangeFlag,
    MemoVersion,
    Review,
    Role,
    User,
)
from services.audit import record_audit_event
from services.composition.provider import CompositionError, CompositionProvider
from services.diff_note.provider import DiffNoteError, DiffNoteProvider
from services.memo import (
    MemoLockedError,
    MemoStateError,
    approve_memo,
    create_memo_from_analysis,
    create_new_version_from_approved,
    override_assumption_and_recompute,
    submit_for_review,
)
from services.review import list_review_queue

router = APIRouter(tags=["memos"])

_ANY_ROLE = (Role.OWNER, Role.ANALYST, Role.APPROVER, Role.VIEWER)
_ANALYST_ROLES = (Role.OWNER, Role.ANALYST)
_APPROVER_ROLES = (Role.OWNER, Role.APPROVER)


def _fmt(value: object | None) -> str | None:
    return None if value is None else str(value)


def _assumptions_for(session: Session, memo_version_id: uuid.UUID) -> list[Assumption]:
    return list(
        session.execute(
            select(Assumption).where(Assumption.memo_version_id == memo_version_id)
        ).scalars()
    )


def _reviews_for(session: Session, memo_version_id: uuid.UUID) -> list[Review]:
    return list(
        session.execute(
            select(Review).where(Review.memo_version_id == memo_version_id)
        ).scalars()
    )


def _stale_reasons_for(session: Session, memo_version_id: uuid.UUID) -> list[str]:
    return list(
        session.execute(
            select(MemoInputChangeFlag.description).where(
                MemoInputChangeFlag.memo_version_id == memo_version_id
            )
        ).scalars()
    )


def _version_out(session: Session, version: MemoVersion) -> MemoVersionOut:
    stale_reasons = _stale_reasons_for(session, version.id)
    assumptions = _assumptions_for(session, version.id)
    reviews = _reviews_for(session, version.id)
    return MemoVersionOut(
        id=version.id,
        memo_id=version.memo_id,
        version=version.version,
        status=version.status.value,
        content=version.content,
        confidence_grade=version.confidence_grade,
        submitted_at=version.submitted_at,
        approved_at=version.approved_at,
        approved_by_user_id=version.approved_by_user_id,
        created_by_user_id=version.created_by_user_id,
        created_at=version.created_at,
        assumptions=[AssumptionOut.model_validate(a) for a in assumptions],
        reviews=[ReviewOut.model_validate(r) for r in reviews],
        inputs_changed=bool(stale_reasons),
        stale_reasons=stale_reasons,
    )


def _memo_out(session: Session, memo: Memo) -> MemoOut:
    versions = session.execute(
        select(MemoVersion).where(MemoVersion.memo_id == memo.id).order_by(MemoVersion.version)
    ).scalars()
    return MemoOut(
        id=memo.id,
        workspace_id=memo.workspace_id,
        analysis_id=memo.analysis_id,
        title=memo.title,
        created_by_user_id=memo.created_by_user_id,
        created_at=memo.created_at,
        used_in_ic=memo.used_in_ic,
        versions=[_version_out(session, v) for v in versions],
    )


def _get_memo_or_404(session: Session, memo_id: uuid.UUID, workspace_id: uuid.UUID) -> Memo:
    memo = session.get(Memo, memo_id)
    if memo is None or memo.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memo not found")
    return memo


def _get_memo_version_or_404(
    session: Session, memo: Memo, version_id: uuid.UUID
) -> MemoVersion:
    version = session.get(MemoVersion, version_id)
    if version is None or version.memo_id != memo.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memo version not found")
    return version


@router.post(
    "/workspaces/{workspace_id}/memos", response_model=MemoOut, status_code=status.HTTP_201_CREATED
)
async def create_memo(
    body: MemoCreateRequest,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(*_ANALYST_ROLES)),
    session: Session = Depends(get_workspace_db),
    composition_provider: CompositionProvider = Depends(get_composition_provider),
) -> MemoOut:
    analysis = session.get(Analysis, body.analysis_id)
    if analysis is None or analysis.workspace_id != membership.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    try:
        memo = create_memo_from_analysis(
            session,
            analysis=analysis,
            tenant_id=membership.tenant_id,
            workspace_id=membership.workspace_id,
            title=body.title,
            created_by_user_id=current_user.id,
            composition_provider=composition_provider,
        )
    except CompositionError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="memo.created",
        entity_type="memo",
        entity_id=memo.id,
        payload={"analysis_id": str(analysis.id)},
    )
    session.commit()
    return _memo_out(session, memo)


@router.get(
    "/workspaces/{workspace_id}/memos/review-queue", response_model=list[ReviewQueueEntryOut]
)
async def get_review_queue(
    membership: Membership = Depends(require_role(*_ANY_ROLE)),
    session: Session = Depends(get_workspace_db),
) -> list[ReviewQueueEntryOut]:
    """F7: Draft/In Review memos for this workspace, low-confidence and
    ambiguous-heavy ones first. Registered ahead of GET /memos/{memo_id}
    so "review-queue" is never mistaken for a memo id."""
    queue = list_review_queue(session, membership.workspace_id)
    return [
        ReviewQueueEntryOut(
            memo_id=entry.memo_id,
            memo_title=entry.memo_title,
            version_id=entry.version_id,
            version_number=entry.version_number,
            status=entry.status.value,
            confidence_grade=entry.confidence_grade,
            ambiguous_count=entry.ambiguous_count,
            submitted_at=entry.submitted_at,
            created_at=entry.created_at,
        )
        for entry in queue
    ]


@router.get("/workspaces/{workspace_id}/memos/{memo_id}", response_model=MemoOut)
async def get_memo(
    memo_id: uuid.UUID,
    membership: Membership = Depends(require_role(*_ANY_ROLE)),
    session: Session = Depends(get_workspace_db),
) -> MemoOut:
    memo = _get_memo_or_404(session, memo_id, membership.workspace_id)
    return _memo_out(session, memo)


@router.get("/workspaces/{workspace_id}/memos", response_model=list[MemoOut])
async def list_memos(
    membership: Membership = Depends(require_role(*_ANY_ROLE)),
    session: Session = Depends(get_workspace_db),
) -> list[MemoOut]:
    memos = session.execute(
        select(Memo)
        .where(Memo.workspace_id == membership.workspace_id)
        .order_by(Memo.created_at.desc())
    ).scalars()
    return [_memo_out(session, memo) for memo in memos]


@router.patch("/workspaces/{workspace_id}/memos/{memo_id}/used-in-ic", response_model=MemoOut)
async def set_memo_used_in_ic(
    memo_id: uuid.UUID,
    body: UsedInIcRequest,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(*_ANALYST_ROLES)),
    session: Session = Depends(get_workspace_db),
) -> MemoOut:
    """F10's used-in-IC board metric tag — a plain field on the mutable
    Memo pointer, not any (possibly approved/immutable) version."""
    memo = _get_memo_or_404(session, memo_id, membership.workspace_id)
    memo.used_in_ic = body.used_in_ic
    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="memo.used_in_ic_tagged",
        entity_type="memo",
        entity_id=memo.id,
        payload={"used_in_ic": body.used_in_ic},
    )
    session.commit()
    return _memo_out(session, memo)


@router.patch(
    "/workspaces/{workspace_id}/memos/{memo_id}/versions/{version_id}/assumptions/{assumption_id}",
    response_model=AssumptionOverrideResponse,
)
async def override_memo_assumption(
    memo_id: uuid.UUID,
    version_id: uuid.UUID,
    assumption_id: uuid.UUID,
    body: AssumptionOverrideRequest,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(*_ANALYST_ROLES)),
    session: Session = Depends(get_workspace_db),
    diff_note_provider: DiffNoteProvider = Depends(get_diff_note_provider),
) -> AssumptionOverrideResponse:
    memo = _get_memo_or_404(session, memo_id, membership.workspace_id)
    version = _get_memo_version_or_404(session, memo, version_id)
    assumption = session.get(Assumption, assumption_id)
    if assumption is None or assumption.memo_version_id != version.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assumption not found")

    try:
        updated_version, diff_note, changes = override_assumption_and_recompute(
            session,
            memo_version=version,
            assumption=assumption,
            new_value=body.value,
            note=body.note,
            diff_note_provider=diff_note_provider,
        )
    except MemoLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except DiffNoteError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="memo.assumption_overridden",
        entity_type="memo_version",
        entity_id=updated_version.id,
        payload={"assumption_key": assumption.key},
    )
    session.commit()

    return AssumptionOverrideResponse(
        version=_version_out(session, updated_version),
        change_note=diff_note.change_note,
        changes=[
            ChangeOut(
                field=change.field,
                kind=change.kind.value,
                before=_fmt(change.before),
                after=_fmt(change.after),
                delta=_fmt(change.delta),
            )
            for change in changes
        ],
    )


@router.post(
    "/workspaces/{workspace_id}/memos/{memo_id}/versions/{version_id}/submit",
    response_model=MemoVersionOut,
)
async def submit_memo_version(
    memo_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(*_ANALYST_ROLES)),
    session: Session = Depends(get_workspace_db),
) -> MemoVersionOut:
    memo = _get_memo_or_404(session, memo_id, membership.workspace_id)
    version = _get_memo_version_or_404(session, memo, version_id)
    try:
        submit_for_review(version)
    except MemoStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="memo.submitted_for_review",
        entity_type="memo_version",
        entity_id=version.id,
    )
    session.commit()
    return _version_out(session, version)


@router.post(
    "/workspaces/{workspace_id}/memos/{memo_id}/versions/{version_id}/approve",
    response_model=MemoVersionOut,
)
async def approve_memo_version(
    memo_id: uuid.UUID,
    version_id: uuid.UUID,
    body: ApproveMemoRequest = ApproveMemoRequest(),
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(*_APPROVER_ROLES)),
    session: Session = Depends(get_workspace_db),
) -> MemoVersionOut:
    memo = _get_memo_or_404(session, memo_id, membership.workspace_id)
    version = _get_memo_version_or_404(session, memo, version_id)
    try:
        approve_memo(
            session,
            memo_version=version,
            approved_by_user_id=current_user.id,
            panel_firm=body.panel_firm,
        )
    except MemoStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="memo.approved",
        entity_type="memo_version",
        entity_id=version.id,
    )
    session.commit()
    return _version_out(session, version)


@router.post(
    "/workspaces/{workspace_id}/memos/{memo_id}/versions/{version_id}/new-version",
    response_model=MemoVersionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_memo_new_version(
    memo_id: uuid.UUID,
    version_id: uuid.UUID,
    body: NewVersionRequest,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(*_ANALYST_ROLES)),
    session: Session = Depends(get_workspace_db),
) -> MemoVersionOut:
    memo = _get_memo_or_404(session, memo_id, membership.workspace_id)
    base_version = _get_memo_version_or_404(session, memo, version_id)
    try:
        new_version = create_new_version_from_approved(
            session,
            memo=memo,
            base_version=base_version,
            change_note=body.change_note,
            created_by_user_id=current_user.id,
        )
    except MemoStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="memo.new_version_created",
        entity_type="memo_version",
        entity_id=new_version.id,
        payload={"superseded_version": base_version.version},
    )
    session.commit()
    return _version_out(session, new_version)

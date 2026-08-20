import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_raw_session
from api.schemas import TenantCreate, TenantOut, WorkspaceCreate, WorkspaceOut
from db.models import Membership, MembershipStatus, Role, Tenant, User, Workspace
from db.session import set_rls_context, set_user_context, tenant_session
from services.audit import record_audit_event

router = APIRouter(tags=["tenants"])


@router.get("/tenants", response_model=list[TenantOut])
async def list_my_tenants(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_raw_session),
) -> list[Tenant]:
    """Every tenant this Clerk identity can act in — the one place the app
    looks up "which organisations does this user belong to" from the
    database, rather than trusting client-side state.

    Before this route existed, the frontend's only record of "which tenant
    is mine" was a tenant id cached in the browser's localStorage — nothing
    server-side ever told a returning user which tenant(s) they already
    belonged to. A cleared browser, a new device, or a different browser
    profile lost that cached id, landed the user on the "create an
    organisation" screen, and a brand new (empty) tenant got created —
    their real one, and everything in it, was never deleted, just no
    longer reachable from the UI. Listing every tenant the user actually
    has a claim on here — not just the last one the browser happened to
    remember — is what makes that class of "my assessments disappeared"
    impossible going forward.

    A user has a claim on a tenant either by being its creator (covers a
    tenant with no workspace/membership yet) or by holding an active
    membership in one of its workspaces — set_user_context (not
    set_rls_context) is what lets the raw session read the caller's own
    membership rows here without already knowing a tenant to scope to;
    see memberships_self_read in the row_level_security migration history.
    """
    set_user_context(session, current_user.id)
    member_tenant_ids = list(
        session.execute(
            select(Membership.tenant_id).where(
                Membership.user_id == current_user.id,
                Membership.status == MembershipStatus.ACTIVE,
            )
        ).scalars()
    )

    tenants = (
        session.execute(
            select(Tenant)
            .where(
                (Tenant.created_by_user_id == current_user.id)
                | (Tenant.id.in_(member_tenant_ids))
            )
            .order_by(Tenant.created_at)
        )
        .scalars()
        .all()
    )
    return list(tenants)


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: TenantCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_raw_session),
) -> Tenant:
    tenant = Tenant(name=body.name, slug=body.slug, created_by_user_id=current_user.id)
    session.add(tenant)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        detail = "An organisation with that slug already exists"
        raise HTTPException(status.HTTP_409_CONFLICT, detail) from exc

    set_rls_context(session, tenant.id, None)
    record_audit_event(
        session,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        action="tenant.created",
        entity_type="tenant",
        entity_id=tenant.id,
        payload={"name": tenant.name, "slug": tenant.slug},
    )
    session.commit()
    session.refresh(tenant)
    return tenant


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
async def get_tenant(
    tenant_id: uuid.UUID,
    _current_user: User = Depends(get_current_user),
    session: Session = Depends(get_raw_session),
) -> Tenant:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    return tenant


def _can_create_workspace(session: Session, tenant: Tenant, user: User) -> bool:
    if tenant.created_by_user_id == user.id:
        return True
    set_rls_context(session, tenant.id, None)
    existing = session.execute(
        select(Membership.id).where(
            Membership.tenant_id == tenant.id,
            Membership.user_id == user.id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    ).first()
    return existing is not None


@router.post(
    "/tenants/{tenant_id}/workspaces",
    response_model=WorkspaceOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    tenant_id: uuid.UUID,
    body: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_raw_session),
) -> WorkspaceOut:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    if not _can_create_workspace(session, tenant, current_user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the organisation's creator or an existing member can add an assessment",
        )

    set_rls_context(session, tenant.id, None)
    workspace = Workspace(
        tenant_id=tenant.id,
        codename=body.codename,
        real_name=body.real_name,
        created_by_user_id=current_user.id,
    )
    session.add(workspace)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "An assessment with that name already exists in this organisation",
        ) from exc

    # Narrow to the new workspace for its first membership + audit rows.
    set_rls_context(session, tenant.id, workspace.id)
    membership = Membership(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=current_user.id,
        invited_email=current_user.email,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
        invited_by_user_id=current_user.id,
    )
    session.add(membership)
    record_audit_event(
        session,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        actor_user_id=current_user.id,
        action="workspace.created",
        entity_type="workspace",
        entity_id=workspace.id,
        payload={"codename": workspace.codename},
    )
    record_audit_event(
        session,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        actor_user_id=current_user.id,
        action="membership.granted",
        entity_type="membership",
        entity_id=membership.id,
        payload={"role": Role.OWNER.value, "user_id": str(current_user.id)},
    )
    session.commit()
    session.refresh(workspace)
    out = WorkspaceOut.model_validate(workspace)
    out.my_role = Role.OWNER
    return out


@router.get("/tenants/{tenant_id}/workspaces", response_model=list[WorkspaceOut])
async def list_my_workspaces_in_tenant(
    tenant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> list[WorkspaceOut]:
    """Only workspaces the caller is an active member of — not every
    workspace in the tenant, so a non-member can't enumerate a tenant's
    other deal codenames just by knowing the tenant id."""
    with tenant_session(tenant_id) as scoped:
        rows = scoped.execute(
            select(Workspace, Membership.role)
            .join(Membership, Membership.workspace_id == Workspace.id)
            .where(
                Membership.user_id == current_user.id,
                Membership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Workspace.created_at)
        ).all()
    results = []
    for workspace, role in rows:
        out = WorkspaceOut.model_validate(workspace)
        out.my_role = role
        results.append(out)
    return results

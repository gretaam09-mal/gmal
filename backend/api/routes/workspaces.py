import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_workspace_db, get_workspace_membership, require_role
from api.schemas import (
    MembershipInvite,
    MembershipInviteOut,
    MembershipOut,
    MembershipRoleUpdate,
    WorkspaceOut,
)
from db.models import AuditEvent, Membership, MembershipStatus, Role, User, Workspace
from services.audit import record_audit_event
from services.email.invites import send_invite_email
from services.invites import create_invite_token

router = APIRouter(tags=["workspaces"])


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    membership: Membership = Depends(get_workspace_membership),
    session: Session = Depends(get_workspace_db),
) -> WorkspaceOut:
    workspace = session.get(Workspace, membership.workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    out = WorkspaceOut.model_validate(workspace)
    out.my_role = membership.role
    return out


@router.get("/workspaces/{workspace_id}/members", response_model=list[MembershipOut])
async def list_members(
    membership: Membership = Depends(get_workspace_membership),
    session: Session = Depends(get_workspace_db),
) -> list[Membership]:
    return list(
        session.execute(
            select(Membership)
            .where(Membership.workspace_id == membership.workspace_id)
            .order_by(Membership.created_at)
        ).scalars()
    )


@router.post(
    "/workspaces/{workspace_id}/members",
    response_model=MembershipInviteOut,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    body: MembershipInvite,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(Role.OWNER)),
    session: Session = Depends(get_workspace_db),
) -> MembershipInviteOut:
    invite = Membership(
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        invited_email=body.email,
        role=body.role,
        status=MembershipStatus.INVITED,
        invited_by_user_id=current_user.id,
    )
    session.add(invite)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That email is already invited to this workspace"
        ) from exc

    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="membership.invited",
        entity_type="membership",
        entity_id=invite.id,
        payload={"invited_email": body.email, "role": body.role.value},
    )
    session.commit()
    session.refresh(invite)

    token = create_invite_token(
        tenant_id=invite.tenant_id, workspace_id=invite.workspace_id, membership_id=invite.id
    )
    invite_url = f"/invites/accept?token={token}"
    send_invite_email(to=body.email, workspace_codename="", invite_url=invite_url)
    out = MembershipOut.model_validate(invite)
    return MembershipInviteOut(membership=out, invite_url=invite_url)


@router.patch("/workspaces/{workspace_id}/members/{membership_id}", response_model=MembershipOut)
async def update_member_role(
    membership_id: uuid.UUID,
    body: MembershipRoleUpdate,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(Role.OWNER)),
    session: Session = Depends(get_workspace_db),
) -> Membership:
    target = session.get(Membership, membership_id)
    if target is None or target.workspace_id != membership.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    previous_role = target.role
    target.role = body.role
    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="membership.role_changed",
        entity_type="membership",
        entity_id=target.id,
        payload={"from": previous_role.value, "to": body.role.value},
    )
    session.commit()
    session.refresh(target)
    return target


@router.delete(
    "/workspaces/{workspace_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_member(
    membership_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(Role.OWNER)),
    session: Session = Depends(get_workspace_db),
) -> None:
    target = session.get(Membership, membership_id)
    if target is None or target.workspace_id != membership.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    target.status = MembershipStatus.REVOKED
    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="membership.revoked",
        entity_type="membership",
        entity_id=target.id,
        payload={"invited_email": target.invited_email},
    )
    session.commit()


@router.get("/workspaces/{workspace_id}/audit-events")
async def list_audit_events(
    membership: Membership = Depends(get_workspace_membership),
    session: Session = Depends(get_workspace_db),
) -> list[dict]:
    events = session.execute(
        select(AuditEvent)
        .where(AuditEvent.workspace_id == membership.workspace_id)
        .order_by(AuditEvent.created_at.desc())
    ).scalars()
    return [
        {
            "id": str(event.id),
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": str(event.entity_id) if event.entity_id else None,
            "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]

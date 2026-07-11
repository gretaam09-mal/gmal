from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_current_user
from api.schemas import InviteAcceptRequest, MembershipOut
from db.models import Membership, MembershipStatus, User
from db.session import workspace_session
from services.audit import record_audit_event
from services.invites import InviteTokenError, verify_invite_token

router = APIRouter(tags=["invites"])


@router.post("/invites/accept", response_model=MembershipOut)
async def accept_invite(
    body: InviteAcceptRequest, current_user: User = Depends(get_current_user)
) -> Membership:
    try:
        claims = verify_invite_token(body.token)
    except InviteTokenError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    with workspace_session(claims.tenant_id, claims.workspace_id) as session:
        membership = session.get(Membership, claims.membership_id)
        if membership is None or membership.workspace_id != claims.workspace_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
        if membership.status != MembershipStatus.INVITED:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "This invite has already been used or revoked"
            )
        if membership.invited_email.lower() != current_user.email.lower():
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "This invite was sent to a different email address"
            )

        membership.user_id = current_user.id
        membership.status = MembershipStatus.ACTIVE
        record_audit_event(
            session,
            tenant_id=membership.tenant_id,
            workspace_id=membership.workspace_id,
            actor_user_id=current_user.id,
            action="membership.accepted",
            entity_type="membership",
            entity_id=membership.id,
            payload={"role": membership.role.value},
        )
        session.commit()
        session.refresh(membership)
        return membership

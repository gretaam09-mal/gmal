"""Shared by F9's sweep notifications and F10's error-register
disclosures: who to email about something that happened in a workspace.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Membership, MembershipStatus, Role
from db.session import set_rls_context


def workspace_owner_emails(
    session: Session, *, tenant_id: uuid.UUID, workspace_id: uuid.UUID
) -> list[str]:
    set_rls_context(session, tenant_id, workspace_id)
    return list(
        session.execute(
            select(Membership.invited_email).where(
                Membership.workspace_id == workspace_id,
                Membership.role == Role.OWNER,
                Membership.status == MembershipStatus.ACTIVE,
            )
        ).scalars()
    )

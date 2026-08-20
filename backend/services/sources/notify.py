"""F9: a plain email naming every memo a sweep just flagged "inputs
changed", one per affected workspace, sent to that workspace's owners.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from services.notifications.email import EmailMessage, EmailProvider
from services.notifications.recipients import workspace_owner_emails
from services.sources.sweep import FlaggedMemo, SweepChange


def notify_affected_memos(
    session: Session, email_provider: EmailProvider, changes: list[SweepChange]
) -> list[EmailMessage]:
    by_workspace: dict[uuid.UUID, list[FlaggedMemo]] = {}
    for change in changes:
        for flagged in change.flagged_memos:
            by_workspace.setdefault(flagged.workspace_id, []).append(flagged)

    messages: list[EmailMessage] = []
    for workspace_id, flagged_memos in by_workspace.items():
        tenant_id = flagged_memos[0].tenant_id
        recipients = workspace_owner_emails(
            session, tenant_id=tenant_id, workspace_id=workspace_id
        )
        memo_lines = "\n".join(f"- {memo.memo_title}" for memo in flagged_memos)
        body = (
            "The following approved memos in your assessment now show \"inputs "
            "changed\", because a regulatory source they relied on was updated:\n\n"
            f"{memo_lines}\n\n"
            "Open each memo to review what changed, then re-run it once the "
            "updated source has been reviewed."
        )
        for recipient in recipients:
            message = EmailMessage(
                to=recipient,
                subject="Provision: inputs changed for memos in your assessment",
                body=body,
            )
            email_provider.send(message)
            messages.append(message)
    return messages

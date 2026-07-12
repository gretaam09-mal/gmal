"""F10's internal error register: post-approval errors worth tracking to
resolution, with root cause, affected clients, and a disclosure record.
Plain mutable rows (not append-only) — a single incident accrues root
cause and disclosure details as staff triage it, rather than each
update being a new immutable fact.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ErrorRegisterEntry
from services.notifications.email import EmailMessage, EmailProvider
from services.notifications.recipients import workspace_owner_emails


def create_error_entry(
    session: Session,
    *,
    source: str,
    message: str,
    context: dict | None = None,
    tenant_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
) -> ErrorRegisterEntry:
    entry = ErrorRegisterEntry(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        source=source,
        message=message,
        context=context,
    )
    session.add(entry)
    session.flush()
    return entry


def list_error_entries(
    session: Session, *, resolved: bool | None = None
) -> list[ErrorRegisterEntry]:
    query = select(ErrorRegisterEntry).order_by(ErrorRegisterEntry.created_at.desc())
    if resolved is True:
        query = query.where(ErrorRegisterEntry.resolved_at.is_not(None))
    elif resolved is False:
        query = query.where(ErrorRegisterEntry.resolved_at.is_(None))
    return list(session.execute(query).scalars())


def set_root_cause(
    session: Session, *, entry: ErrorRegisterEntry, root_cause: str
) -> ErrorRegisterEntry:
    entry.root_cause = root_cause
    session.flush()
    return entry


def add_affected_workspace(
    session: Session, *, entry: ErrorRegisterEntry, workspace_id: uuid.UUID
) -> ErrorRegisterEntry:
    workspace_id_str = str(workspace_id)
    if workspace_id_str not in entry.affected_workspace_ids:
        entry.affected_workspace_ids = [*entry.affected_workspace_ids, workspace_id_str]
        session.flush()
    return entry


def resolve_error_entry(session: Session, *, entry: ErrorRegisterEntry) -> ErrorRegisterEntry:
    entry.resolved_at = datetime.now(UTC)
    session.flush()
    return entry


def send_disclosure(
    session: Session,
    *,
    entry: ErrorRegisterEntry,
    disclosure_note: str,
    email_provider: EmailProvider,
    affected_tenant_ids_by_workspace: dict[str, uuid.UUID],
) -> tuple[ErrorRegisterEntry, list[EmailMessage]]:
    """Records the disclosure and emails every affected workspace's
    owners naming what happened — the disclosure obligation F10 exists
    to support. `affected_tenant_ids_by_workspace` maps each of
    entry.affected_workspace_ids to its tenant_id, since the register
    itself only stores workspace ids (see the model docstring) and a
    tenant-scoped read needs both to look up recipients."""
    entry.disclosure_note = disclosure_note
    entry.disclosure_sent_at = datetime.now(UTC)
    session.flush()

    messages: list[EmailMessage] = []
    for workspace_id_str in entry.affected_workspace_ids:
        tenant_id = affected_tenant_ids_by_workspace.get(workspace_id_str)
        if tenant_id is None:
            continue
        recipients = workspace_owner_emails(
            session, tenant_id=tenant_id, workspace_id=uuid.UUID(workspace_id_str)
        )
        for recipient in recipients:
            message = EmailMessage(
                to=recipient,
                subject="Provision: disclosure notice",
                body=disclosure_note,
            )
            email_provider.send(message)
            messages.append(message)
    return entry, messages

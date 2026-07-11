import uuid

from sqlalchemy.orm import Session

from db.models import AuditEvent


def record_audit_event(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    action: str,
    entity_type: str,
    workspace_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    payload: dict | None = None,
) -> AuditEvent:
    """Write one append-only audit event.

    CONVENTIONS.md rule #2 + F1 success criterion: every state change
    writes an audit event. Call this in the same transaction as the
    mutation it records, so a rollback can never leave a mutation without
    its audit trail (or an audit trail without its mutation).
    """
    event = AuditEvent(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
    )
    session.add(event)
    session.flush()
    return event

"""F10 — the internal error register. Staff-only (require_staff), like
api/routes/admin_instruments.py and api/routes/admin_metrics.py: post-
approval errors, root cause, affected clients and disclosure are
internal ops data, never exposed on a tenant-facing route.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_raw_session, require_staff
from api.schemas import (
    AddAffectedWorkspaceRequest,
    ErrorEntryCreateRequest,
    ErrorEntryOut,
    SendDisclosureRequest,
    SetRootCauseRequest,
)
from db.models import ErrorRegisterEntry, User
from services.error_register import (
    add_affected_workspace,
    create_error_entry,
    list_error_entries,
    resolve_error_entry,
    send_disclosure,
    set_root_cause,
)
from services.notifications.email import StubEmailProvider

router = APIRouter(prefix="/admin", tags=["admin-error-register"])


def _get_entry_or_404(session: Session, entry_id: uuid.UUID) -> ErrorRegisterEntry:
    entry = session.get(ErrorRegisterEntry, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Error register entry not found")
    return entry


@router.post(
    "/error-register", response_model=ErrorEntryOut, status_code=status.HTTP_201_CREATED
)
async def create_error_register_entry(
    body: ErrorEntryCreateRequest,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> ErrorEntryOut:
    entry = create_error_entry(
        session,
        source=body.source,
        message=body.message,
        context=body.context,
        tenant_id=body.tenant_id,
        workspace_id=body.workspace_id,
    )
    session.commit()
    return ErrorEntryOut.model_validate(entry)


@router.get("/error-register", response_model=list[ErrorEntryOut])
async def get_error_register_entries(
    resolved: bool | None = None,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> list[ErrorEntryOut]:
    entries = list_error_entries(session, resolved=resolved)
    return [ErrorEntryOut.model_validate(entry) for entry in entries]


@router.patch("/error-register/{entry_id}/root-cause", response_model=ErrorEntryOut)
async def patch_error_register_root_cause(
    entry_id: uuid.UUID,
    body: SetRootCauseRequest,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> ErrorEntryOut:
    entry = _get_entry_or_404(session, entry_id)
    set_root_cause(session, entry=entry, root_cause=body.root_cause)
    session.commit()
    return ErrorEntryOut.model_validate(entry)


@router.post("/error-register/{entry_id}/affected-workspaces", response_model=ErrorEntryOut)
async def post_error_register_affected_workspace(
    entry_id: uuid.UUID,
    body: AddAffectedWorkspaceRequest,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> ErrorEntryOut:
    entry = _get_entry_or_404(session, entry_id)
    add_affected_workspace(session, entry=entry, workspace_id=body.workspace_id)
    session.commit()
    return ErrorEntryOut.model_validate(entry)


@router.post("/error-register/{entry_id}/resolve", response_model=ErrorEntryOut)
async def post_error_register_resolve(
    entry_id: uuid.UUID,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> ErrorEntryOut:
    entry = _get_entry_or_404(session, entry_id)
    resolve_error_entry(session, entry=entry)
    session.commit()
    return ErrorEntryOut.model_validate(entry)


@router.post("/error-register/{entry_id}/disclose", response_model=ErrorEntryOut)
async def post_error_register_disclose(
    entry_id: uuid.UUID,
    body: SendDisclosureRequest,
    _staff: User = Depends(require_staff),
    session: Session = Depends(get_raw_session),
) -> ErrorEntryOut:
    entry = _get_entry_or_404(session, entry_id)
    entry, _messages = send_disclosure(
        session,
        entry=entry,
        disclosure_note=body.disclosure_note,
        email_provider=StubEmailProvider(),
        affected_tenant_ids_by_workspace=body.affected_tenant_ids_by_workspace,
    )
    session.commit()
    return ErrorEntryOut.model_validate(entry)

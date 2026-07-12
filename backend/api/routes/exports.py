"""F8 — the memo's exportable forms: a print-styled HTML preview (the
route Chromium screenshots into a PDF), a PDF carrying the memo, the
assumption register, and a lineage appendix, and a DOCX of the memo body
for an IC pack. All three read from the same MemoVersion.content the
on-screen Impact Memo reads from, so exports always match what a
reviewer approved.
"""

import uuid
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_workspace_db, require_role
from db.models import Assumption, Membership, Memo, MemoVersion, Report, Role, User
from services.audit import record_audit_event
from services.exports.docx import render_memo_docx
from services.exports.html import render_memo_html
from services.exports.lineage_query import build_lineage_appendix
from services.exports.pdf import render_html_to_pdf

router = APIRouter(tags=["exports"])

_ANY_ROLE = (Role.OWNER, Role.ANALYST, Role.APPROVER, Role.VIEWER)


def _get_memo_or_404(session: Session, memo_id: uuid.UUID, workspace_id: uuid.UUID) -> Memo:
    memo = session.get(Memo, memo_id)
    if memo is None or memo.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memo not found")
    return memo


def _get_memo_version_or_404(session: Session, memo: Memo, version_id: uuid.UUID) -> MemoVersion:
    version = session.get(MemoVersion, version_id)
    if version is None or version.memo_id != memo.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memo version not found")
    return version


def _assumption_dicts(session: Session, version_id: uuid.UUID) -> list[dict]:
    rows = session.execute(
        select(Assumption).where(Assumption.memo_version_id == version_id)
    ).scalars()
    return [{"key": a.key, "value": a.value, "source": a.source, "note": a.note} for a in rows]


def _content_disposition(filename: str) -> str:
    """Memo titles are free text and may contain non-latin-1 characters
    (em dashes, etc.), which HTTP headers can't carry directly — RFC 5987
    filename* is the standard escape hatch, with an ASCII fallback for
    clients that only read the plain filename param."""
    ascii_fallback = filename.encode("ascii", errors="replace").decode("ascii")
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{quote(filename)}'


def _rendered_html(session: Session, memo: Memo, version: MemoVersion) -> str:
    lineage = build_lineage_appendix(session, version)
    assumptions = _assumption_dicts(session, version.id)
    return render_memo_html(
        memo_title=memo.title, content=version.content, assumptions=assumptions, lineage=lineage
    )


def _record_report(
    session: Session,
    *,
    membership: Membership,
    current_user: User,
    version: MemoVersion,
    report_type: str,
) -> None:
    storage_key = f"memo-versions/{version.id}/{report_type}-{datetime.now(UTC).isoformat()}"
    session.add(
        Report(
            tenant_id=membership.tenant_id,
            workspace_id=membership.workspace_id,
            memo_version_id=version.id,
            report_type=report_type,
            storage_key=storage_key,
            generated_by_user_id=current_user.id,
        )
    )
    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action=f"memo.exported.{report_type}",
        entity_type="memo_version",
        entity_id=version.id,
    )
    session.commit()


@router.get(
    "/workspaces/{workspace_id}/memos/{memo_id}/versions/{version_id}/print-preview",
    response_class=Response,
)
async def print_preview_memo_version(
    memo_id: uuid.UUID,
    version_id: uuid.UUID,
    membership: Membership = Depends(require_role(*_ANY_ROLE)),
    session: Session = Depends(get_workspace_db),
) -> Response:
    """The print-styled HTML route: the single source both a human
    previewing in a browser and headless Chromium's PDF render read
    from, so the two always match exactly."""
    memo = _get_memo_or_404(session, memo_id, membership.workspace_id)
    version = _get_memo_version_or_404(session, memo, version_id)
    html = _rendered_html(session, memo, version)
    return Response(content=html, media_type="text/html")


@router.get(
    "/workspaces/{workspace_id}/memos/{memo_id}/versions/{version_id}/export.pdf",
)
def export_memo_version_pdf(
    memo_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(*_ANY_ROLE)),
    session: Session = Depends(get_workspace_db),
) -> Response:
    # Plain def, not async def: render_html_to_pdf uses Playwright's sync
    # API, which refuses to run inside an already-running asyncio loop.
    # FastAPI runs sync route handlers in a worker thread, sidestepping that.
    memo = _get_memo_or_404(session, memo_id, membership.workspace_id)
    version = _get_memo_version_or_404(session, memo, version_id)
    html = _rendered_html(session, memo, version)
    pdf_bytes = render_html_to_pdf(html)
    _record_report(
        session,
        membership=membership,
        current_user=current_user,
        version=version,
        report_type="pdf",
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition(f"{memo.title}.pdf")},
    )


@router.get(
    "/workspaces/{workspace_id}/memos/{memo_id}/versions/{version_id}/export.docx",
)
async def export_memo_version_docx(
    memo_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(*_ANY_ROLE)),
    session: Session = Depends(get_workspace_db),
) -> Response:
    memo = _get_memo_or_404(session, memo_id, membership.workspace_id)
    version = _get_memo_version_or_404(session, memo, version_id)
    docx_bytes = render_memo_docx(memo_title=memo.title, content=version.content)
    _record_report(
        session,
        membership=membership,
        current_user=current_user,
        version=version,
        report_type="docx",
    )
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _content_disposition(f"{memo.title}.docx")},
    )

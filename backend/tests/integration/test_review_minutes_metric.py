"""F7 acceptance test: approving a memo automatically captures review-
minutes as a board metric — no separate timer, no manual entry."""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from db.models import Memo, MemoVersion, MetricsEvent, Review, Tenant, Workspace
from db.models.enums import MemoStatus
from db.session import set_rls_context
from services.memo import approve_memo
from services.metrics import REVIEW_COMPLETED_EVENT


def _bare_memo_version_in_review(db_session, make_user, *, submitted_at):
    owner = make_user()
    tenant = Tenant(name="Fund A", slug=f"fund-{uuid.uuid4().hex[:8]}", created_by_user_id=owner.id)
    db_session.add(tenant)
    db_session.flush()
    set_rls_context(db_session, tenant.id, None)
    workspace = Workspace(
        tenant_id=tenant.id, codename="project-falcon", created_by_user_id=owner.id
    )
    db_session.add(workspace)
    db_session.flush()
    set_rls_context(db_session, tenant.id, workspace.id)
    memo = Memo(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        title="Test memo",
        created_by_user_id=owner.id,
    )
    db_session.add(memo)
    db_session.flush()
    memo_version = MemoVersion(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        memo_id=memo.id,
        version=1,
        content={},
        status=MemoStatus.IN_REVIEW,
        submitted_at=submitted_at,
        created_by_user_id=owner.id,
    )
    db_session.add(memo_version)
    db_session.flush()
    db_session.commit()
    return memo_version


def test_approve_memo_records_review_minutes_metric(client_as, make_user, db_session):
    submitted_at = datetime.now(UTC) - timedelta(minutes=42)
    memo_version = _bare_memo_version_in_review(db_session, make_user, submitted_at=submitted_at)
    reviewer = make_user()

    approve_memo(
        db_session,
        memo_version=memo_version,
        approved_by_user_id=reviewer.id,
        panel_firm="Outside Counsel LLP",
    )
    db_session.commit()

    review = (
        db_session.query(Review).filter(Review.memo_version_id == memo_version.id).one()
    )
    assert review.reviewer_user_id == reviewer.id
    assert review.panel_firm == "Outside Counsel LLP"

    events = db_session.execute(
        select(MetricsEvent).where(MetricsEvent.event_name == REVIEW_COMPLETED_EVENT)
    ).scalars().all()
    matching = [e for e in events if e.properties["memo_version_id"] == str(memo_version.id)]
    assert len(matching) == 1
    event = matching[0]
    assert event.properties["reviewer_user_id"] == str(reviewer.id)
    # Allow slack for wall-clock time elapsed while the test itself ran.
    assert 41.9 <= event.properties["review_minutes"] <= 43.0

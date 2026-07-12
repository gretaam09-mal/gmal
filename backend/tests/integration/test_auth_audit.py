from sqlalchemy import select

import api.deps as deps
from db.models import AuditEvent, User
from services.auth.clerk import ClerkClaims


def _fake_verify_clerk_token(monkeypatch, *, clerk_user_id: str, email: str | None):
    monkeypatch.setattr(
        deps,
        "verify_clerk_token",
        lambda token: ClerkClaims(clerk_user_id=clerk_user_id, email=email),
    )


def test_first_sign_in_creates_a_platform_level_audit_event(monkeypatch, db_session):
    _fake_verify_clerk_token(monkeypatch, clerk_user_id="clerk_abc123", email="new@example.com")

    user = deps.get_current_user(authorization="Bearer whatever", session=db_session)

    assert user.email == "new@example.com"
    events = db_session.execute(
        select(AuditEvent).where(AuditEvent.action == "auth.first_sign_in")
    ).scalars().all()
    assert len(events) == 1
    assert events[0].tenant_id is None
    assert events[0].workspace_id is None
    assert events[0].actor_user_id == user.id
    assert events[0].entity_id == user.id


def test_repeat_sign_in_does_not_duplicate_the_audit_event(monkeypatch, db_session):
    _fake_verify_clerk_token(monkeypatch, clerk_user_id="clerk_repeat", email="repeat@example.com")

    first = deps.get_current_user(authorization="Bearer whatever", session=db_session)
    second = deps.get_current_user(authorization="Bearer whatever", session=db_session)

    assert first.id == second.id
    events = db_session.execute(
        select(AuditEvent).where(AuditEvent.action == "auth.first_sign_in")
    ).scalars().all()
    assert len(events) == 1

    users = db_session.execute(
        select(User).where(User.clerk_user_id == "clerk_repeat")
    ).scalars().all()
    assert len(users) == 1

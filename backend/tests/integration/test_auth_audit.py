from dataclasses import dataclass, field

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


@dataclass
class _FakeSettings:
    admin_emails_list: list[str] = field(default_factory=list)


def _fake_admin_emails(monkeypatch, *emails: str):
    monkeypatch.setattr(deps, "get_settings", lambda: _FakeSettings(admin_emails_list=list(emails)))


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


def test_sign_in_with_an_allowlisted_email_elevates_to_staff(monkeypatch, db_session):
    _fake_verify_clerk_token(monkeypatch, clerk_user_id="clerk_admin", email="owner@example.com")
    _fake_admin_emails(monkeypatch, "owner@example.com")

    user = deps.get_current_user(authorization="Bearer whatever", session=db_session)

    assert user.is_staff is True
    events = db_session.execute(
        select(AuditEvent).where(AuditEvent.action == "auth.staff_granted_via_admin_emails")
    ).scalars().all()
    assert len(events) == 1
    assert events[0].tenant_id is None
    assert events[0].actor_user_id == user.id
    assert events[0].entity_id == user.id


def test_admin_emails_match_is_case_insensitive(monkeypatch, db_session):
    _fake_verify_clerk_token(monkeypatch, clerk_user_id="clerk_admin2", email="Owner@Example.com")
    _fake_admin_emails(monkeypatch, "owner@example.com")

    user = deps.get_current_user(authorization="Bearer whatever", session=db_session)

    assert user.is_staff is True


def test_sign_in_with_an_unlisted_email_does_not_elevate(monkeypatch, db_session):
    _fake_verify_clerk_token(monkeypatch, clerk_user_id="clerk_plain", email="nobody@example.com")
    _fake_admin_emails(monkeypatch, "owner@example.com")

    user = deps.get_current_user(authorization="Bearer whatever", session=db_session)

    assert user.is_staff is False
    events = db_session.execute(
        select(AuditEvent).where(AuditEvent.action == "auth.staff_granted_via_admin_emails")
    ).scalars().all()
    assert len(events) == 0


def test_repeat_sign_in_does_not_duplicate_the_elevation_audit_event(monkeypatch, db_session):
    """Idempotent: elevation happens once, not on every subsequent sign-in
    while the email stays on the list."""
    _fake_verify_clerk_token(monkeypatch, clerk_user_id="clerk_admin3", email="owner3@example.com")
    _fake_admin_emails(monkeypatch, "owner3@example.com")

    first = deps.get_current_user(authorization="Bearer whatever", session=db_session)
    second = deps.get_current_user(authorization="Bearer whatever", session=db_session)

    assert first.id == second.id
    assert second.is_staff is True
    events = db_session.execute(
        select(AuditEvent).where(AuditEvent.action == "auth.staff_granted_via_admin_emails")
    ).scalars().all()
    assert len(events) == 1


def test_elevation_never_demotes_a_staff_user_removed_from_the_list(monkeypatch, db_session):
    """Elevation-only: being dropped from PROVISION_ADMIN_EMAILS must never
    auto-revoke staff access that was already granted (by this mechanism or
    by scripts/grant_staff.py) — only a deliberate --revoke does that."""
    _fake_verify_clerk_token(monkeypatch, clerk_user_id="clerk_admin4", email="owner4@example.com")
    _fake_admin_emails(monkeypatch, "owner4@example.com")
    user = deps.get_current_user(authorization="Bearer whatever", session=db_session)
    assert user.is_staff is True

    # now the email is no longer on the list (e.g. removed from the env var)
    _fake_admin_emails(monkeypatch)
    user = deps.get_current_user(authorization="Bearer whatever", session=db_session)

    assert user.is_staff is True


def test_elevation_only_touches_is_staff(monkeypatch, db_session):
    _fake_verify_clerk_token(monkeypatch, clerk_user_id="clerk_admin5", email="owner5@example.com")
    _fake_admin_emails(monkeypatch, "owner5@example.com")

    user = deps.get_current_user(authorization="Bearer whatever", session=db_session)

    assert user.email == "owner5@example.com"
    assert user.clerk_user_id == "clerk_admin5"


def test_a_user_created_with_no_email_claim_gets_a_placeholder(monkeypatch, db_session):
    """Clerk's session token doesn't always carry an email claim (depends
    on the Clerk Dashboard's session token customization — see
    docs/runbooks/clerk-setup.md); when it's absent, first sign-in still
    has to produce a row with *some* unique, valid email."""
    _fake_verify_clerk_token(monkeypatch, clerk_user_id="clerk_no_email", email=None)

    user = deps.get_current_user(authorization="Bearer whatever", session=db_session)

    assert user.email == "clerk_no_email@users.provision.invalid"


def test_a_later_sign_in_with_a_real_email_syncs_it_and_elevates_without_sign_out(
    monkeypatch, db_session
):
    """The exact scenario a user hits if Clerk's session token didn't
    carry an email claim when they first signed in (so their row got the
    synthetic placeholder), and only later starts sending a real one
    (e.g. once the Dashboard's session token customization is fixed) —
    the very next request must sync the real email AND elevate off it in
    one pass, with no sign-out or new Clerk session required."""
    _fake_verify_clerk_token(monkeypatch, clerk_user_id="clerk_late_email", email=None)
    first = deps.get_current_user(authorization="Bearer whatever", session=db_session)
    assert first.email == "clerk_late_email@users.provision.invalid"
    assert first.is_staff is False

    _fake_verify_clerk_token(
        monkeypatch, clerk_user_id="clerk_late_email", email="late@example.com"
    )
    _fake_admin_emails(monkeypatch, "late@example.com")

    second = deps.get_current_user(authorization="Bearer whatever", session=db_session)

    assert second.id == first.id
    assert second.email == "late@example.com"
    assert second.is_staff is True


def test_sign_in_never_overwrites_a_real_email_with_a_missing_claim(monkeypatch, db_session):
    """A later request whose token happens to lack the email claim (or any
    transient decoding hiccup) must never blank out or clobber an email
    already on file."""
    _fake_verify_clerk_token(
        monkeypatch, clerk_user_id="clerk_stable_email", email="stable@example.com"
    )
    first = deps.get_current_user(authorization="Bearer whatever", session=db_session)
    assert first.email == "stable@example.com"

    _fake_verify_clerk_token(monkeypatch, clerk_user_id="clerk_stable_email", email=None)
    second = deps.get_current_user(authorization="Bearer whatever", session=db_session)

    assert second.email == "stable@example.com"

from dataclasses import dataclass, field

import api.deps as deps
import api.routes.me as me_route


@dataclass
class _FakeSettings:
    admin_emails_list: list[str] = field(default_factory=list)


def _fake_admin_emails(monkeypatch, *emails: str):
    settings = _FakeSettings(admin_emails_list=list(emails))
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    monkeypatch.setattr(me_route, "get_settings", lambda: settings)


def test_me_self_diagnoses_when_admin_emails_is_unset(client_as, make_user, monkeypatch):
    _fake_admin_emails(monkeypatch)
    user = make_user(email="plain@example.com")
    client = client_as(user)

    resp = client.get("/me")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_staff"] is False
    assert body["admin_emails_configured"] is False
    assert body["email_matches_admin_list"] is False


def test_me_self_diagnoses_an_email_not_on_an_otherwise_configured_list(
    client_as, make_user, monkeypatch
):
    _fake_admin_emails(monkeypatch, "someone-else@example.com")
    user = make_user(email="plain@example.com")
    client = client_as(user)

    resp = client.get("/me")

    body = resp.json()
    assert body["is_staff"] is False
    assert body["admin_emails_configured"] is True
    assert body["email_matches_admin_list"] is False


def test_me_reports_a_matching_and_elevated_admin_email(
    client_as, make_user, db_session, monkeypatch
):
    """client_as overrides get_current_user with a test-only identity
    lookup (see conftest.py), which bypasses _maybe_elevate_to_staff — so
    this sets is_staff directly to stand in for "elevation already ran"
    (see test_auth_audit.py for elevation itself) and checks /me's
    self-diagnostic fields report that state correctly."""
    _fake_admin_emails(monkeypatch, "owner@example.com")
    user = make_user(email="owner@example.com")
    user.is_staff = True
    db_session.commit()
    client = client_as(user)

    resp = client.get("/me")

    body = resp.json()
    assert body["is_staff"] is True
    assert body["admin_emails_configured"] is True
    assert body["email_matches_admin_list"] is True

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from db.session import set_rls_context


def _create_tenant(client):
    resp = client.post("/tenants", json={"name": "Fund A", "slug": f"fund-{uuid.uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_workspace(client, tenant_id, codename):
    resp = client.post(f"/tenants/{tenant_id}/workspaces", json={"codename": codename})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_every_state_change_is_audit_logged(client_as, make_user):
    owner = make_user()
    invitee = make_user()
    owner_client = client_as(owner)
    invitee_client = client_as(invitee)

    tenant = _create_tenant(owner_client)
    workspace = _create_workspace(owner_client, tenant["id"], "project-falcon")

    invite = owner_client.post(
        f"/workspaces/{workspace['id']}/members", json={"email": invitee.email, "role": "viewer"}
    )
    assert invite.status_code == 201
    token = invite.json()["invite_url"].split("token=")[1]
    membership_id = invite.json()["membership"]["id"]

    accept = invitee_client.post("/invites/accept", json={"token": token})
    assert accept.status_code == 200

    change = owner_client.patch(
        f"/workspaces/{workspace['id']}/members/{membership_id}", json={"role": "analyst"}
    )
    assert change.status_code == 200

    revoke = owner_client.delete(f"/workspaces/{workspace['id']}/members/{membership_id}")
    assert revoke.status_code == 204

    events = owner_client.get(f"/workspaces/{workspace['id']}/audit-events").json()
    actions = [e["action"] for e in events]

    for expected in (
        "workspace.created",
        "membership.granted",
        "membership.invited",
        "membership.accepted",
        "membership.role_changed",
        "membership.revoked",
    ):
        assert expected in actions, f"missing audit event: {expected}"

    role_change_event = next(e for e in events if e["action"] == "membership.role_changed")
    assert role_change_event["payload"] == {"from": "viewer", "to": "analyst"}
    assert role_change_event["actor_user_id"] == str(owner.id)


def test_audit_events_are_immutable(db_session):
    """DB-layer backstop: even a direct UPDATE/DELETE against audit_events
    is rejected, independent of the application never issuing one."""
    owner_id = uuid.uuid4()
    db_session.execute(
        text("INSERT INTO users (id, clerk_user_id, email) VALUES (:id, :c, :e)"),
        {"id": owner_id, "c": f"clerk_{owner_id.hex[:8]}", "e": f"{owner_id.hex[:8]}@example.com"},
    )
    tenant_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO tenants (id, name, slug, created_by_user_id) "
            "VALUES (:id, 'X', :slug, :u)"
        ),
        {"id": tenant_id, "slug": f"x-{tenant_id.hex[:8]}", "u": owner_id},
    )
    set_rls_context(db_session, tenant_id, None)
    db_session.execute(
        text(
            "INSERT INTO audit_events (id, tenant_id, action, entity_type, payload) "
            "VALUES (:id, :t, 'tenant.created', 'tenant', '{}'::jsonb)"
        ),
        {"id": uuid.uuid4(), "t": tenant_id},
    )
    db_session.commit()

    with pytest.raises(ProgrammingError, match="append-only"):
        db_session.execute(text("UPDATE audit_events SET action = 'hacked'"))
        db_session.commit()
    db_session.rollback()

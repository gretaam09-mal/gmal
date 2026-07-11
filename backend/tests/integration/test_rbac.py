import uuid

import pytest


def _create_tenant(client):
    resp = client.post("/tenants", json={"name": "Fund A", "slug": f"fund-{uuid.uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_workspace(client, tenant_id, codename):
    resp = client.post(f"/tenants/{tenant_id}/workspaces", json={"codename": codename})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _invite_and_accept(owner_client, member_client, workspace_id, email, role):
    invite = owner_client.post(
        f"/workspaces/{workspace_id}/members", json={"email": email, "role": role}
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["invite_url"].split("token=")[1]
    accept = member_client.post("/invites/accept", json={"token": token})
    assert accept.status_code == 200, accept.text
    return accept.json()


def _invite_nobody(client, workspace_id):
    return client.post(
        f"/workspaces/{workspace_id}/members",
        json={"email": "nobody@example.com", "role": "viewer"},
    )


def _member_id(client, workspace_id, email):
    members = client.get(f"/workspaces/{workspace_id}/members").json()
    return next(m["id"] for m in members if m["invited_email"] == email)


@pytest.fixture
def workspace_with_all_roles(client_as, make_user):
    """One workspace with an active member in each of the four roles."""
    owner = make_user()
    owner_client = client_as(owner)
    tenant = _create_tenant(owner_client)
    workspace = _create_workspace(owner_client, tenant["id"], "project-falcon")

    users = {"owner": owner}
    clients = {"owner": owner_client}
    for role in ("analyst", "approver", "viewer"):
        user = make_user()
        client = client_as(user)
        _invite_and_accept(owner_client, client, workspace["id"], user.email, role)
        users[role] = user
        clients[role] = client

    return workspace, users, clients


def test_viewer_can_read_but_not_invite(workspace_with_all_roles):
    workspace, _users, clients = workspace_with_all_roles

    read = clients["viewer"].get(f"/workspaces/{workspace['id']}")
    assert read.status_code == 200
    assert _invite_nobody(clients["viewer"], workspace["id"]).status_code == 403


def test_analyst_cannot_invite_or_change_roles(workspace_with_all_roles):
    workspace, users, clients = workspace_with_all_roles

    assert _invite_nobody(clients["analyst"], workspace["id"]).status_code == 403

    viewer_id = _member_id(clients["owner"], workspace["id"], users["viewer"].email)
    change_role = clients["analyst"].patch(
        f"/workspaces/{workspace['id']}/members/{viewer_id}", json={"role": "owner"}
    )
    assert change_role.status_code == 403


def test_approver_cannot_invite(workspace_with_all_roles):
    workspace, _users, clients = workspace_with_all_roles
    assert _invite_nobody(clients["approver"], workspace["id"]).status_code == 403


def test_owner_can_invite_and_change_roles(workspace_with_all_roles):
    workspace, users, clients = workspace_with_all_roles

    analyst_id = _member_id(clients["owner"], workspace["id"], users["analyst"].email)
    change_role = clients["owner"].patch(
        f"/workspaces/{workspace['id']}/members/{analyst_id}", json={"role": "approver"}
    )
    assert change_role.status_code == 200
    assert change_role.json()["role"] == "approver"


def test_revoked_member_loses_access(workspace_with_all_roles):
    workspace, users, clients = workspace_with_all_roles

    viewer_id = _member_id(clients["owner"], workspace["id"], users["viewer"].email)
    revoke = clients["owner"].delete(f"/workspaces/{workspace['id']}/members/{viewer_id}")
    assert revoke.status_code == 204

    now_blocked = clients["viewer"].get(f"/workspaces/{workspace['id']}")
    assert now_blocked.status_code == 404


def test_non_member_gets_404_not_403(client_as, make_user, workspace_with_all_roles):
    workspace, _users, _clients = workspace_with_all_roles
    outsider = make_user()
    outsider_client = client_as(outsider)

    resp = outsider_client.get(f"/workspaces/{workspace['id']}")
    assert resp.status_code == 404

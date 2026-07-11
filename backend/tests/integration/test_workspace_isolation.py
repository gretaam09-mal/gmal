import uuid


def _create_tenant(client, name="Fund A"):
    resp = client.post("/tenants", json={"name": name, "slug": f"fund-{uuid.uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_workspace(client, tenant_id, codename):
    resp = client.post(f"/tenants/{tenant_id}/workspaces", json={"codename": codename})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _invite_and_accept(owner_client, member_client, workspace_id, email, role="analyst"):
    invite = owner_client.post(
        f"/workspaces/{workspace_id}/members", json={"email": email, "role": role}
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["invite_url"].split("token=")[1]
    accept = member_client.post("/invites/accept", json={"token": token})
    assert accept.status_code == 200, accept.text
    return accept.json()


def test_two_workspaces_in_one_tenant_are_fully_isolated(client_as, make_user):
    owner = make_user()
    member = make_user()

    owner_client = client_as(owner)
    member_client = client_as(member)

    tenant = _create_tenant(owner_client)
    falcon = _create_workspace(owner_client, tenant["id"], "project-falcon")
    osprey = _create_workspace(owner_client, tenant["id"], "project-osprey")

    _invite_and_accept(owner_client, member_client, falcon["id"], member.email)

    # The invited member can see the workspace they were added to.
    ok = member_client.get(f"/workspaces/{falcon['id']}")
    assert ok.status_code == 200
    assert ok.json()["codename"] == "project-falcon"

    # ...but the second workspace in the SAME tenant is invisible to them —
    # not 403 (which would confirm it exists), a 404.
    hidden = member_client.get(f"/workspaces/{osprey['id']}")
    assert hidden.status_code == 404

    # Membership listing for falcon is also invisible from a request that
    # doesn't belong to that workspace.
    hidden_members = member_client.get(f"/workspaces/{osprey['id']}/members")
    assert hidden_members.status_code == 404

    # And listing "my workspaces in this tenant" only shows falcon for
    # the member, while the owner sees both.
    member_list = member_client.get(f"/tenants/{tenant['id']}/workspaces")
    assert {w["codename"] for w in member_list.json()} == {"project-falcon"}

    owner_list = owner_client.get(f"/tenants/{tenant['id']}/workspaces")
    assert {w["codename"] for w in owner_list.json()} == {"project-falcon", "project-osprey"}


def test_audit_events_are_isolated_per_workspace(client_as, make_user):
    owner = make_user()
    member = make_user()
    owner_client = client_as(owner)
    member_client = client_as(member)

    tenant = _create_tenant(owner_client)
    falcon = _create_workspace(owner_client, tenant["id"], "project-falcon")
    osprey = _create_workspace(owner_client, tenant["id"], "project-osprey")
    _invite_and_accept(owner_client, member_client, falcon["id"], member.email)

    falcon_events = owner_client.get(f"/workspaces/{falcon['id']}/audit-events")
    assert falcon_events.status_code == 200
    actions = {e["action"] for e in falcon_events.json()}
    assert "workspace.created" in actions
    assert "membership.accepted" in actions
    # osprey's events (its own workspace.created) must not leak into falcon's log.
    assert all(e["entity_id"] != osprey["id"] for e in falcon_events.json())

    hidden = member_client.get(f"/workspaces/{osprey['id']}/audit-events")
    assert hidden.status_code == 404

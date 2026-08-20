"""Reproduces the actual reported bug: "my assessments keep disappearing".

get_current_user (api/deps.py) already keys the Clerk -> User mapping on
the stable clerk_user_id claim, not email, and never creates a duplicate
User row on repeat sign-in — see test_auth_audit.py's
test_repeat_sign_in_does_not_duplicate_the_audit_event, which already pins
that. The real bug was one level up: there was no backend query for
"which tenant(s) does this user belong to" at all. The only place that
was ever recorded was a tenant id cached in the browser's own
localStorage (WorkspaceDashboard.tsx) — nothing server-side. A cleared
browser, a new device, or a different browser profile lost that cached
id, the frontend showed "create an organisation" as if the user had never
signed up, and a brand new (empty) tenant got created — the user's real
tenant, and every assessment in it, was never deleted, just unreachable
from the UI.

These tests exercise GET /tenants (the fix) across two independent
TestClient instances authenticated as the *same* underlying user with no
state shared between them whatsoever — standing in for "the same person,
logging in again from a browser/device that remembers nothing" (a cleared
cache, a new device, or a frontend redeploy), which is exactly the
scenario the bug report describes.
"""
import uuid


def _create_tenant(client, name="Fund A"):
    resp = client.post("/tenants", json={"name": name, "slug": f"fund-{uuid.uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_workspace(client, tenant_id, codename):
    resp = client.post(f"/tenants/{tenant_id}/workspaces", json={"codename": codename})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_the_same_identity_resolves_to_the_same_tenant_across_independent_logins(
    client_as, make_user
):
    """The exact scenario from the bug report, made concrete: create an
    organisation and an assessment in one "login", then authenticate again
    as the same person with a brand new client that shares nothing with
    the first — no cookies, no localStorage equivalent, nothing but the
    identity itself — and confirm GET /tenants still finds the same
    organisation, with the assessment still listed inside it."""
    owner = make_user()

    first_login = client_as(owner)
    tenant = _create_tenant(first_login, name="Project Falcon Fund")
    workspace = _create_workspace(first_login, tenant["id"], "project-falcon")

    # A second, fully independent "login" — new TestClient, nothing carried
    # over from the first — for the exact same Clerk identity.
    second_login = client_as(owner)

    my_tenants = second_login.get("/tenants")
    assert my_tenants.status_code == 200, my_tenants.text
    tenant_ids = [t["id"] for t in my_tenants.json()]
    assert tenant_ids == [tenant["id"]], (
        "the same identity must resolve to exactly the one tenant it already "
        "belongs to, not zero (an apparently 'empty' account) and not a "
        "second, duplicate one"
    )

    my_workspaces = second_login.get(f"/tenants/{tenant['id']}/workspaces")
    assert my_workspaces.status_code == 200, my_workspaces.text
    assert [w["codename"] for w in my_workspaces.json()] == [workspace["codename"]], (
        "the assessment created in the first login must still be visible in "
        "the second — it was never deleted, only unreachable before this fix"
    )


def test_a_brand_new_identity_sees_no_tenants_until_it_creates_one(client_as, make_user):
    """The other half of the same guarantee: GET /tenants must not leak
    another user's organisations just because *some* tenant exists in the
    database."""
    someone_else = make_user()
    _create_tenant(client_as(someone_else), name="Someone Else's Fund")

    new_user = make_user()
    resp = client_as(new_user).get("/tenants")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


def test_a_tenant_with_no_workspace_yet_is_still_visible_to_its_creator(client_as, make_user):
    """A tenant the user just created has no Membership row yet (that's
    only created alongside a workspace's first membership) — created_by_
    user_id is what must still surface it, or the very moment between
    "create organisation" and "create first assessment" would itself look
    like an empty account on a second login."""
    owner = make_user()
    tenant = _create_tenant(client_as(owner), name="Brand New Fund")

    second_login = client_as(owner)
    resp = second_login.get("/tenants")

    assert resp.status_code == 200, resp.text
    assert [t["id"] for t in resp.json()] == [tenant["id"]]


def test_multiple_tenants_are_all_listed_not_just_the_most_recent(client_as, make_user):
    """Directly covers the "duplicate/orphaned tenants" consolidation ask:
    if this identity already has more than one tenant (e.g. from hitting
    the bug before this fix shipped), every one of them must come back
    from GET /tenants, not just the latest — so the user can navigate to
    all of them rather than being stuck on whichever one the UI happened
    to default to."""
    owner = make_user()
    first_tenant = _create_tenant(client_as(owner), name="First Fund")
    second_tenant = _create_tenant(client_as(owner), name="Second Fund (orphaned before the fix)")

    resp = client_as(owner).get("/tenants")

    assert resp.status_code == 200, resp.text
    returned_ids = {t["id"] for t in resp.json()}
    assert returned_ids == {first_tenant["id"], second_tenant["id"]}


def test_a_member_without_creating_the_tenant_still_sees_it(client_as, make_user):
    """The creator isn't the only person who should see a tenant — anyone
    holding an active membership in one of its workspaces must too, e.g.
    an invited teammate logging in on their own device for the first
    time."""
    owner = make_user()
    member = make_user()
    owner_client = client_as(owner)
    tenant = _create_tenant(owner_client, name="Shared Fund")
    workspace = _create_workspace(owner_client, tenant["id"], "project-osprey")

    invite = owner_client.post(
        f"/workspaces/{workspace['id']}/members", json={"email": member.email, "role": "analyst"}
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["invite_url"].split("token=")[1]
    accept = client_as(member).post("/invites/accept", json={"token": token})
    assert accept.status_code == 200, accept.text

    member_second_login = client_as(member)
    resp = member_second_login.get("/tenants")

    assert resp.status_code == 200, resp.text
    assert [t["id"] for t in resp.json()] == [tenant["id"]]

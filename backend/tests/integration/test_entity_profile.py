import uuid


def _create_tenant_and_workspace(client, codename="project-falcon"):
    slug = f"fund-{uuid.uuid4().hex[:8]}"
    tenant = client.post("/tenants", json={"name": "Fund A", "slug": slug})
    assert tenant.status_code == 201, tenant.text
    workspace = client.post(
        f"/tenants/{tenant.json()['id']}/workspaces", json={"codename": codename}
    )
    assert workspace.status_code == 201, workspace.text
    return workspace.json()


def test_autofill_populates_identity_officers_sic_and_scale(
    client_as, make_user, companies_house_fixture
):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)

    resp = client.post(
        f"/workspaces/{workspace['id']}/profile/autofill",
        json={"companies_house_number": "12345678"},
    )
    assert resp.status_code == 200, resp.text
    profile = resp.json()

    assert profile["version"] == 1
    assert profile["is_current"] is True
    assert profile["companies_house_number"] == "12345678"

    fields = {f["key"]: f for f in profile["fields"]}
    assert fields["identity.company_name"]["value"] == "EXAMPLE TARGET LIMITED"
    assert fields["identity.company_name"]["source"] == "registry"
    assert len(fields["identity.officers"]["value"]) == 3
    assert fields["activity.sic_codes"]["value"] == ["62012", "62020"]
    assert fields["scale.band"]["value"] == "small"
    assert fields["scale.band"]["source"] == "filing"

    # Footprint/cost-sketch/materiality fields aren't autofillable — they
    # stay unknown and pull completeness down, exactly as the spec wants:
    # unknown never blocks, it just shows up in the completeness meter.
    assert profile["completeness"]["overall_score"] < 1.0
    assert "Operates outside the UK?" in profile["completeness"]["unknown_field_labels"]


def test_autofill_unknown_company_number_is_404(client_as, make_user, companies_house_fixture):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)

    resp = client.post(
        f"/workspaces/{workspace['id']}/profile/autofill",
        json={"companies_house_number": "00000000"},
    )
    assert resp.status_code == 404


def test_update_profile_creates_new_immutable_version_and_carries_forward_fields(
    client_as, make_user, companies_house_fixture
):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)

    autofill = client.post(
        f"/workspaces/{workspace['id']}/profile/autofill",
        json={"companies_house_number": "12345678"},
    )
    assert autofill.status_code == 200
    assert autofill.json()["version"] == 1

    update = client.put(
        f"/workspaces/{workspace['id']}/profile",
        json={
            "fields": [
                {
                    "key": "footprint.processes_personal_data",
                    "value": True,
                    "source": "user",
                    "confirmed_at": "2026-01-01T00:00:00Z",
                }
            ]
        },
    )
    assert update.status_code == 200, update.text
    v2 = update.json()
    assert v2["version"] == 2
    assert v2["is_current"] is True

    fields_v2 = {f["key"]: f for f in v2["fields"]}
    # The new answer is there...
    assert fields_v2["footprint.processes_personal_data"]["value"] is True
    assert fields_v2["footprint.processes_personal_data"]["source"] == "user"
    # ...and everything from the autofill carried forward untouched.
    assert fields_v2["identity.company_name"]["value"] == "EXAMPLE TARGET LIMITED"

    # Version 1 still exists, unmodified, and is no longer current.
    versions = client.get(f"/workspaces/{workspace['id']}/profile/versions").json()
    assert [v["version"] for v in versions] == [2, 1]
    v1 = next(v for v in versions if v["version"] == 1)
    assert v1["is_current"] is False
    fields_v1 = {f["key"]: f for f in v1["fields"]}
    assert "footprint.processes_personal_data" not in fields_v1


def test_unknown_field_is_explicit_not_blocking(client_as, make_user):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)

    resp = client.put(
        f"/workspaces/{workspace['id']}/profile",
        json={
            "fields": [
                {"key": "footprint.holds_client_money", "value": None, "source": "unknown"},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    field = next(f for f in body["fields"] if f["key"] == "footprint.holds_client_money")
    assert field["source"] == "unknown"
    assert field["value"] is None
    assert "Holds client money or assets?" in body["completeness"]["unknown_field_labels"]


def test_viewer_can_read_profile_but_not_update(client_as, make_user, companies_house_fixture):
    owner = make_user()
    viewer = make_user()
    owner_client = client_as(owner)
    viewer_client = client_as(viewer)
    workspace = _create_tenant_and_workspace(owner_client)

    invite = owner_client.post(
        f"/workspaces/{workspace['id']}/members", json={"email": viewer.email, "role": "viewer"}
    )
    token = invite.json()["invite_url"].split("token=")[1]
    assert viewer_client.post("/invites/accept", json={"token": token}).status_code == 200

    owner_client.post(
        f"/workspaces/{workspace['id']}/profile/autofill",
        json={"companies_house_number": "12345678"},
    )

    read = viewer_client.get(f"/workspaces/{workspace['id']}/profile")
    assert read.status_code == 200
    assert read.json()["companies_house_number"] == "12345678"

    write = viewer_client.put(
        f"/workspaces/{workspace['id']}/profile",
        json={"fields": [{"key": "footprint.employs_staff", "value": True, "source": "user"}]},
    )
    assert write.status_code == 403


def test_field_catalog_exposes_footprint_used_for_hints(client_as, make_user):
    owner = make_user()
    client = client_as(owner)

    resp = client.get("/profile-field-catalog")
    assert resp.status_code == 200
    catalog = {f["key"]: f for f in resp.json()}
    assert catalog["footprint.holds_client_money"]["used_for"] == "Triggers FCA client money rules."
    assert catalog["identity.company_name"]["used_for"] is None

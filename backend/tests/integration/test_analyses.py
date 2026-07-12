import uuid
from decimal import Decimal

from db.session import set_rls_context
from services.extraction import ExtractedObligation, FixtureExtractionProvider
from services.instrument_onboarding import (
    approve_obligation,
    approve_predicate,
    attach_cost_template,
    create_predicate,
    extract_obligation,
    ingest_instrument,
    list_clauses,
)
from services.scenarios import ScenarioInput, record_scenario_probabilities

_RAW_TEXT = (
    "1. A firm that processes personal data at scale must appoint a data protection officer."
)


def _create_tenant_and_workspace(client, codename="project-falcon"):
    slug = f"fund-{uuid.uuid4().hex[:8]}"
    tenant = client.post("/tenants", json={"name": "Fund A", "slug": slug})
    assert tenant.status_code == 201, tenant.text
    workspace = client.post(
        f"/tenants/{tenant.json()['id']}/workspaces", json={"codename": codename}
    )
    assert workspace.status_code == 201, workspace.text
    return workspace.json()


def _set_profile_field(client, workspace_id, key, value, source="user"):
    resp = client.put(
        f"/workspaces/{workspace_id}/profile",
        json={"fields": [{"key": key, "value": value, "source": source}]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _approved_predicate_bound_to_new_obligation(
    db_session, make_user, *, expression, in_flight=False, title="Test Data Protection Act"
):
    """Seeds one fully-approved obligation+predicate pair via the service
    layer (not HTTP — this is reference-data setup, not the thing under
    test) and returns (obligation, predicate)."""
    version = ingest_instrument(
        db_session,
        title=title,
        jurisdiction="UK",
        kind="Act",
        citation=None,
        version_label="v1",
        source_url=None,
        raw_text=_RAW_TEXT,
        in_flight=in_flight,
    )
    clause = list_clauses(db_session, version.id)[0]
    extracted = ExtractedObligation.model_validate(
        {
            "summary": "Appoint a data protection officer.",
            "obligation_type": "appointment",
            "who": {
                "value": "firms processing personal data at scale",
                "clause_ref": clause.clause_ref,
                "confidence": 90,
            },
            "what": {"value": "appoint a DPO", "clause_ref": clause.clause_ref, "confidence": 95},
            "when": {"value": "2026-01-01", "clause_ref": clause.clause_ref, "confidence": 50},
            "threshold": {
                "value": "processes personal data at scale",
                "clause_ref": clause.clause_ref,
                "confidence": 85,
            },
            "enforcer": {"value": "the ICO", "clause_ref": clause.clause_ref, "confidence": 80},
            "confidence": 88,
        }
    )
    provider = FixtureExtractionProvider({clause.clause_ref: extracted})
    obligation = extract_obligation(
        db_session, clause=clause, instrument_title="Test Data Protection Act", provider=provider
    )
    staff = make_user()
    approve_obligation(db_session, obligation=obligation, approved_by_user_id=staff.id)

    predicate = create_predicate(
        db_session,
        obligation=obligation,
        predicate_key="processes_personal_data",
        expression=expression,
    )
    approve_predicate(db_session, predicate=predicate, approved_by_user_id=staff.id)
    db_session.commit()
    return obligation, predicate


def test_analysis_binds_and_includes_a_deterministic_rationale(
    client_as, make_user, db_session
):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)

    obligation, predicate = _approved_predicate_bound_to_new_obligation(
        db_session,
        make_user,
        expression={"field": "footprint.processes_personal_data", "equals": True},
    )

    resp = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert resp.status_code == 201, resp.text
    analysis = resp.json()
    assert analysis["status"] == "complete"

    matching = [i for i in analysis["items"] if i["predicate_id"] == str(predicate.id)]
    assert len(matching) == 1
    item = matching[0]
    assert item["outcome"] == "binds"
    assert item["obligation_summary"] == "Appoint a data protection officer."
    assert item["instrument_title"] == "Test Data Protection Act"
    assert item["rationale"].startswith("Binds:")
    assert item["confidence"] == 88
    assert item["first_obligation_date"] == "2026-01-01"
    assert item["memo_status"] == "not_started"


def test_analysis_does_not_bind_rationale_is_first_class(client_as, make_user, db_session):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", False)

    obligation, predicate = _approved_predicate_bound_to_new_obligation(
        db_session,
        make_user,
        expression={"field": "footprint.processes_personal_data", "equals": True},
    )

    resp = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert resp.status_code == 201, resp.text
    item = next(i for i in resp.json()["items"] if i["predicate_id"] == str(predicate.id))
    assert item["outcome"] == "does_not_bind"
    assert item["rationale"].startswith("Does not bind:")
    assert item["amount"] is None


def test_analysis_is_ambiguous_and_names_the_missing_field(client_as, make_user, db_session):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)
    # A profile exists, but footprint.processes_personal_data specifically
    # is never answered — that's the field under test.
    _set_profile_field(client, workspace["id"], "footprint.employs_staff", True)

    obligation, predicate = _approved_predicate_bound_to_new_obligation(
        db_session,
        make_user,
        expression={"field": "footprint.processes_personal_data", "equals": True},
    )

    resp = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert resp.status_code == 201, resp.text
    item = next(i for i in resp.json()["items"] if i["predicate_id"] == str(predicate.id))
    assert item["outcome"] == "ambiguous"
    assert item["missing_field_keys"] == ["footprint.processes_personal_data"]
    assert item["rationale"].startswith("Ambiguous:")


def test_analysis_quantifies_impact_when_bound_and_cost_template_exists(
    client_as, make_user, db_session
):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)
    _set_profile_field(client, workspace["id"], "scale.employee_count", 500)

    obligation, predicate = _approved_predicate_bound_to_new_obligation(
        db_session,
        make_user,
        expression={"field": "footprint.processes_personal_data", "equals": True},
    )
    attach_cost_template(
        db_session,
        obligation=obligation,
        name="DPO cost",
        drivers=[{"key": "scale.employee_count", "label": "Employee count"}],
        formula={"base": 5000, "terms": [{"driver": "scale.employee_count", "rate": 40}]},
        currency="GBP",
        source_basis="expert estimate",
        maturity_tier="rough",
    )
    db_session.commit()

    resp = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert resp.status_code == 201, resp.text
    item = next(i for i in resp.json()["items"] if i["predicate_id"] == str(predicate.id))
    assert item["outcome"] == "binds"
    assert item["amount"] == 5000 + 40 * 500
    assert item["impact_band"] == "£10k–£50k"


def test_analysis_computes_range_phasing_and_present_value(client_as, make_user, db_session):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)
    _set_profile_field(client, workspace["id"], "scale.employee_count", 500)

    obligation, predicate = _approved_predicate_bound_to_new_obligation(
        db_session,
        make_user,
        expression={"field": "footprint.processes_personal_data", "equals": True},
    )
    attach_cost_template(
        db_session,
        obligation=obligation,
        name="DPO cost",
        drivers=[{"key": "scale.employee_count", "label": "Employee count"}],
        formula={"base": 5000, "terms": [{"driver": "scale.employee_count", "rate": 40}]},
        currency="GBP",
        source_basis="expert estimate",
        maturity_tier="rough",
        first_obligation_date="2027-01-01",
        transition_months=2,
    )
    db_session.commit()

    resp = client.post(
        f"/workspaces/{workspace['id']}/analyses", json={"discount_rate_pct": 12}
    )
    assert resp.status_code == 201, resp.text
    item = next(i for i in resp.json()["items"] if i["predicate_id"] == str(predicate.id))
    amount = item["amount"]
    assert amount == 5000 + 40 * 500

    assert item["impact_low"] == round(amount * 0.8, 2)
    assert item["impact_high"] == round(amount * 1.3, 2)

    schedule = item["phased_schedule"]
    assert [entry["period"] for entry in schedule] == ["2027-01", "2027-02", "2027-03"]
    assert round(sum(entry["amount"] for entry in schedule), 2) == round(amount, 2)

    assert item["present_value"] is not None
    assert item["present_value"] < amount  # a positive discount rate always discounts


def test_analysis_weights_in_flight_instrument_scenarios(client_as, make_user, db_session):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)
    _set_profile_field(client, workspace["id"], "scale.employee_count", 500)

    obligation, predicate = _approved_predicate_bound_to_new_obligation(
        db_session,
        make_user,
        expression={"field": "footprint.processes_personal_data", "equals": True},
        in_flight=True,
        title="In-Flight Draft Bill",
    )
    attach_cost_template(
        db_session,
        obligation=obligation,
        name="DPO cost",
        drivers=[{"key": "scale.employee_count", "label": "Employee count"}],
        formula={"base": 5000, "terms": [{"driver": "scale.employee_count", "rate": 40}]},
        currency="GBP",
        source_basis="expert estimate",
        maturity_tier="rough",
    )
    set_rls_context(db_session, workspace["tenant_id"], workspace["id"])
    record_scenario_probabilities(
        db_session,
        tenant_id=uuid.UUID(workspace["tenant_id"]),
        workspace_id=uuid.UUID(workspace["id"]),
        predicate_id=predicate.id,
        inputs=[
            ScenarioInput(
                scenario="as_drafted",
                probability=Decimal("0.5"),
                magnitude_multiplier=Decimal("1.0"),
                source="expert_override",
            ),
            ScenarioInput(
                scenario="amended",
                probability=Decimal("0.5"),
                magnitude_multiplier=Decimal("2.0"),
                source="expert_override",
            ),
        ],
    )
    db_session.commit()

    resp = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert resp.status_code == 201, resp.text
    item = next(i for i in resp.json()["items"] if i["predicate_id"] == str(predicate.id))
    point_amount = 5000 + 40 * 500
    # weighted 50/50 between 1x and 2x the point amount -> 1.5x
    assert item["amount"] == round(point_amount * 1.5, 2)


def test_unapproved_predicate_never_reaches_an_analysis(client_as, make_user, db_session):
    """The F3 success criterion, checked at the F4 boundary: a predicate
    whose obligation isn't approved must never produce an AnalysisItem,
    even though the predicate itself is a real APPROVED predicate."""
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)

    version = ingest_instrument(
        db_session,
        title="Unapproved Act",
        jurisdiction="UK",
        kind="Act",
        citation=None,
        version_label="v1",
        source_url=None,
        raw_text=_RAW_TEXT,
    )
    clause = list_clauses(db_session, version.id)[0]
    extracted = ExtractedObligation.model_validate(
        {
            "summary": "An unapproved obligation.",
            "obligation_type": "appointment",
            "who": {"value": "x", "clause_ref": clause.clause_ref, "confidence": 50},
            "what": {"value": "x", "clause_ref": clause.clause_ref, "confidence": 50},
            "when": {"value": "x", "clause_ref": clause.clause_ref, "confidence": 50},
            "threshold": {"value": "x", "clause_ref": clause.clause_ref, "confidence": 50},
            "enforcer": {"value": "x", "clause_ref": clause.clause_ref, "confidence": 50},
            "confidence": 50,
        }
    )
    provider = FixtureExtractionProvider({clause.clause_ref: extracted})
    obligation = extract_obligation(
        db_session, clause=clause, instrument_title="Unapproved Act", provider=provider
    )
    # Deliberately never approved.
    predicate = create_predicate(
        db_session,
        obligation=obligation,
        predicate_key="always_true",
        expression={"field": "footprint.processes_personal_data", "equals": True},
    )
    db_session.commit()

    resp = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert resp.status_code == 201, resp.text
    matching = [i for i in resp.json()["items"] if i["predicate_id"] == str(predicate.id)]
    assert matching == []


def test_viewer_cannot_trigger_an_analysis(client_as, make_user, db_session):
    owner = make_user()
    viewer_user = make_user()
    owner_client = client_as(owner)
    viewer_client = client_as(viewer_user)
    workspace = _create_tenant_and_workspace(owner_client)

    invite = owner_client.post(
        f"/workspaces/{workspace['id']}/members",
        json={"email": viewer_user.email, "role": "viewer"},
    )
    assert invite.status_code == 201
    token = invite.json()["invite_url"].split("token=")[1]
    accept = viewer_client.post("/invites/accept", json={"token": token})
    assert accept.status_code == 200

    resp = viewer_client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert resp.status_code == 403


def test_analysis_without_a_profile_yet_is_a_clear_conflict_not_a_crash(client_as, make_user):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)

    resp = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert resp.status_code == 409

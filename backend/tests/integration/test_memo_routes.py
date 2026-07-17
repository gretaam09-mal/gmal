import uuid

from services.composition.schemas import ComposedMemoProse
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


def _invite_and_accept(owner_client, member_client, workspace_id, email, role):
    invite = owner_client.post(
        f"/workspaces/{workspace_id}/members", json={"email": email, "role": role}
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["invite_url"].split("token=")[1]
    accept = member_client.post("/invites/accept", json={"token": token})
    assert accept.status_code == 200, accept.text
    return accept.json()


def _set_profile_field(client, workspace_id, key, value, source="user"):
    resp = client.put(
        f"/workspaces/{workspace_id}/profile",
        json={"fields": [{"key": key, "value": value, "source": source}]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _approved_predicate_bound_to_new_obligation(db_session, make_user, *, expression):
    version = ingest_instrument(
        db_session,
        title="Test Data Protection Act",
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


def _memo_prose(predicate_id: str) -> ComposedMemoProse:
    return ComposedMemoProse.model_validate(
        {
            "headline_summary": "This deal carries a bounded, quantified regulatory exposure.",
            "obligations": [
                {
                    "predicate_id": predicate_id,
                    "what_it_requires": "Appoint a data protection officer.",
                    "why_it_applies": "The target processes personal data at scale.",
                }
            ],
            "excluded_summary": "No obligations were excluded from this analysis.",
        }
    )


def _create_memo_via_http(client, workspace, composition_provider, predicate):
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)
    _set_profile_field(client, workspace["id"], "scale.employee_count", 500)
    analysis = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert analysis.status_code == 201, analysis.text

    composition_provider.register(str(predicate.id), _memo_prose(str(predicate.id)))
    resp = client.post(
        f"/workspaces/{workspace['id']}/memos",
        json={"analysis_id": analysis.json()["id"], "title": "Project Falcon — Impact Memo"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_full_memo_lifecycle_over_http(
    client_as, make_user, db_session, composition_provider_fixture, diff_note_provider_fixture
):
    owner = make_user()
    owner_client = client_as(owner)
    workspace = _create_tenant_and_workspace(owner_client)

    approver = make_user()
    approver_client = client_as(approver)
    _invite_and_accept(owner_client, approver_client, workspace["id"], approver.email, "approver")

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

    memo = _create_memo_via_http(owner_client, workspace, composition_provider_fixture, predicate)
    memo_id = memo["id"]
    version = memo["versions"][0]
    assert version["status"] == "draft"
    obligation_entry = next(
        o for o in version["content"]["obligations"] if o["predicate_id"] == str(predicate.id)
    )
    assert obligation_entry["impact_likely"] == str(5000 + 40 * 500)
    assert obligation_entry["what_it_requires"] == "Appoint a data protection officer."

    # The frontend renders instrument_title in the Composition-of-the-
    # range legend and obligation_summary as the Obligations heading —
    # they must actually be different strings in the real API response,
    # not just in a hand-written frontend fixture, or the two sections
    # repeat the same sentence on screen (the reported live-app bug).
    assert obligation_entry["instrument_title"] == "Test Data Protection Act"
    assert obligation_entry["instrument_title"] != obligation_entry["obligation_summary"]

    # A number in the memo traces to its clauses/figures in a handful of
    # clicks: get memo -> read obligation section -> see clause_refs.
    assert obligation_entry["clause_refs"]

    # override the employee-count driver assumption and recompute
    driver_key = f"driver:{predicate.id}:scale.employee_count"
    driver_assumption = next(a for a in version["assumptions"] if a["key"] == driver_key)
    override = owner_client.patch(
        f"/workspaces/{workspace['id']}/memos/{memo_id}/versions/{version['id']}"
        f"/assumptions/{driver_assumption['id']}",
        json={"value": {"value": "1000"}, "note": "Revised headcount"},
    )
    assert override.status_code == 200, override.text
    override_body = override.json()
    new_obligation_entry = next(
        o
        for o in override_body["version"]["content"]["obligations"]
        if o["predicate_id"] == str(predicate.id)
    )
    assert new_obligation_entry["impact_likely"] == str(5000 + 40 * 1000)
    assert override_body["change_note"]
    assert override_body["changes"]

    # viewer cannot submit for review
    viewer = make_user()
    viewer_client = client_as(viewer)
    _invite_and_accept(owner_client, viewer_client, workspace["id"], viewer.email, "viewer")
    forbidden = viewer_client.post(
        f"/workspaces/{workspace['id']}/memos/{memo_id}/versions/{version['id']}/submit"
    )
    assert forbidden.status_code == 403

    submitted = owner_client.post(
        f"/workspaces/{workspace['id']}/memos/{memo_id}/versions/{version['id']}/submit"
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "in_review"

    # an analyst-only owner cannot self-approve via a role that lacks it —
    # here the owner *can* (OWNER carries every permission); check that
    # the approver role can too.
    approved = approver_client.post(
        f"/workspaces/{workspace['id']}/memos/{memo_id}/versions/{version['id']}/approve"
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by_user_id"] == str(approver.id)

    # approved memo versions cannot be overridden any further
    locked = owner_client.patch(
        f"/workspaces/{workspace['id']}/memos/{memo_id}/versions/{version['id']}"
        f"/assumptions/{driver_assumption['id']}",
        json={"value": {"value": "1"}},
    )
    assert locked.status_code == 409

    # a further change creates a new version, not a mutation
    new_version = owner_client.post(
        f"/workspaces/{workspace['id']}/memos/{memo_id}/versions/{version['id']}/new-version",
        json={"change_note": "Recomputed after updated accounts."},
    )
    assert new_version.status_code == 201, new_version.text
    assert new_version.json()["version"] == 2
    assert new_version.json()["status"] == "draft"


def test_correct_memo_obligation_and_cost_template_over_http(
    client_as, make_user, db_session, composition_provider_fixture
):
    """No prior test called these two routes over HTTP (see
    test_review_corrections.py, which only exercises the underlying
    services/review.py functions directly) — only a real HTTP round trip
    proves CorrectionOut serialization actually works, the way the
    in_flight bug in admin_instruments.py proved this class of gap is
    real (see test_instrument_onboarding.py)."""
    owner = make_user()
    owner_client = client_as(owner)
    workspace = _create_tenant_and_workspace(owner_client)

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

    memo = _create_memo_via_http(owner_client, workspace, composition_provider_fixture, predicate)
    version_id = memo["versions"][0]["id"]

    # Cost-template correction first, while `obligation.id` is still the
    # current version — obligation correction below closes this id
    # (bitemporal versioning supersedes it with a new row/id), so it must
    # run second or this lookup would 404 against the now-stale id.
    cost_template_correction = owner_client.post(
        f"/workspaces/{workspace['id']}/memos/{memo['id']}/versions/{version_id}"
        f"/obligations/{obligation.id}/cost-template/correct",
        json={
            "name": "DPO cost (revised)",
            "drivers": [{"key": "scale.employee_count", "label": "Employee count"}],
            "formula": {"base": 8000, "terms": [{"driver": "scale.employee_count", "rate": 45}]},
            "currency": "GBP",
            "source_basis": "vendor quote",
            "maturity_tier": "quoted",
            "note": "Vendor quote came in higher than the initial estimate.",
        },
    )
    assert cost_template_correction.status_code == 201, cost_template_correction.text
    template_correction_body = cost_template_correction.json()
    assert template_correction_body["memo_version_id"] == version_id
    assert template_correction_body["cost_template_id"] is not None
    assert template_correction_body["obligation_id"] is None
    assert (
        template_correction_body["note"]
        == "Vendor quote came in higher than the initial estimate."
    )

    obligation_correction = owner_client.post(
        f"/workspaces/{workspace['id']}/memos/{memo['id']}/versions/{version_id}"
        f"/obligations/{obligation.id}/correct",
        json={
            "summary": "Appoint a data protection officer within 30 days.",
            "obligation_type": "appointment",
            "fields": {k: v for k, v in obligation.fields.items()},
            "confidence": 95,
            "note": "The original extraction missed the 30-day deadline.",
        },
    )
    assert obligation_correction.status_code == 201, obligation_correction.text
    correction_body = obligation_correction.json()
    assert correction_body["memo_version_id"] == version_id
    assert correction_body["obligation_id"] is not None
    assert correction_body["cost_template_id"] is None
    assert correction_body["corrected_by_user_id"] == str(owner.id)
    assert correction_body["note"] == "The original extraction missed the 30-day deadline."


def test_viewer_cannot_create_a_memo(
    client_as, make_user, db_session, composition_provider_fixture
):
    owner = make_user()
    owner_client = client_as(owner)
    workspace = _create_tenant_and_workspace(owner_client)

    viewer = make_user()
    viewer_client = client_as(viewer)
    _invite_and_accept(owner_client, viewer_client, workspace["id"], viewer.email, "viewer")

    _set_profile_field(owner_client, workspace["id"], "footprint.processes_personal_data", True)
    analysis = owner_client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert analysis.status_code == 201, analysis.text

    resp = viewer_client.post(
        f"/workspaces/{workspace['id']}/memos",
        json={"analysis_id": analysis.json()["id"], "title": "Should be forbidden"},
    )
    assert resp.status_code == 403

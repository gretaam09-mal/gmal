"""Re-runnability bug: re-running analysis after a profile edit created a
fresh Analysis/AnalysisItem rows (proving the exposure list was already
correct — see test_analyses.py), but nothing ever re-pointed an existing
Memo.analysis_id at the new analysis or recomputed its content, so the
Impact Memo silently kept showing the superseded run's numbers forever.
These tests exercise the fix over real HTTP: change a profile field ->
re-run -> the memo reflects the change, for both the Draft (regenerate in
place) and Approved (new version with a diff) cases.
"""

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


def _setup_workspace_with_bound_obligation(client, db_session, make_user):
    workspace = _create_tenant_and_workspace(client)
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
    return workspace, obligation, predicate


def test_rerun_after_profile_edit_regenerates_a_draft_memo(
    client_as, make_user, db_session, composition_provider_fixture
):
    owner = make_user()
    client = client_as(owner)
    workspace, obligation, predicate = _setup_workspace_with_bound_obligation(
        client, db_session, make_user
    )

    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)
    _set_profile_field(client, workspace["id"], "scale.employee_count", 500)
    analysis = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert analysis.status_code == 201, analysis.text
    first_analysis_id = analysis.json()["id"]

    composition_provider_fixture.register(str(predicate.id), _memo_prose(str(predicate.id)))
    memo_resp = client.post(
        f"/workspaces/{workspace['id']}/memos",
        json={"analysis_id": first_analysis_id, "title": "Project Falcon — Impact Memo"},
    )
    assert memo_resp.status_code == 201, memo_resp.text
    memo = memo_resp.json()
    original_obligation = next(
        o
        for o in memo["versions"][0]["content"]["obligations"]
        if o["predicate_id"] == str(predicate.id)
    )
    assert original_obligation["impact_likely"] == str(5000 + 40 * 500)

    # The bug: update the profile (headcount grows) and re-run — the
    # exposure list already picked up new employee counts (see
    # test_analyses.py), but before this fix the memo's own numbers
    # never moved off the first analysis's figures.
    _set_profile_field(client, workspace["id"], "scale.employee_count", 900)
    rerun = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert rerun.status_code == 201, rerun.text
    second_analysis_id = rerun.json()["id"]
    assert second_analysis_id != first_analysis_id
    rerun_item = next(i for i in rerun.json()["items"] if i["predicate_id"] == str(predicate.id))
    assert rerun_item["amount"] == 5000 + 40 * 900

    memo_after = client.get(f"/workspaces/{workspace['id']}/memos/{memo['id']}")
    assert memo_after.status_code == 200, memo_after.text
    memo_after_body = memo_after.json()
    # Same memo, same (single) draft version — regenerated in place, not
    # a new memo and not a new version.
    assert memo_after_body["id"] == memo["id"]
    assert memo_after_body["analysis_id"] == second_analysis_id
    assert len(memo_after_body["versions"]) == 1
    updated_version = memo_after_body["versions"][0]
    assert updated_version["status"] == "draft"
    updated_obligation = next(
        o
        for o in updated_version["content"]["obligations"]
        if o["predicate_id"] == str(predicate.id)
    )
    assert updated_obligation["impact_likely"] == str(5000 + 40 * 900)


def test_rerun_after_profile_edit_branches_a_new_version_from_an_approved_memo(
    client_as, make_user, db_session, composition_provider_fixture, diff_note_provider_fixture
):
    owner = make_user()
    client = client_as(owner)
    workspace, obligation, predicate = _setup_workspace_with_bound_obligation(
        client, db_session, make_user
    )

    approver = make_user()
    approver_client = client_as(approver)
    invite = client.post(
        f"/workspaces/{workspace['id']}/members",
        json={"email": approver.email, "role": "approver"},
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["invite_url"].split("token=")[1]
    accept = approver_client.post("/invites/accept", json={"token": token})
    assert accept.status_code == 200, accept.text

    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)
    _set_profile_field(client, workspace["id"], "scale.employee_count", 500)
    analysis = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert analysis.status_code == 201, analysis.text

    composition_provider_fixture.register(str(predicate.id), _memo_prose(str(predicate.id)))
    memo_resp = client.post(
        f"/workspaces/{workspace['id']}/memos",
        json={"analysis_id": analysis.json()["id"], "title": "Project Falcon — Impact Memo"},
    )
    assert memo_resp.status_code == 201, memo_resp.text
    memo = memo_resp.json()
    version_id = memo["versions"][0]["id"]

    submitted = client.post(
        f"/workspaces/{workspace['id']}/memos/{memo['id']}/versions/{version_id}/submit"
    )
    assert submitted.status_code == 200, submitted.text
    approved = approver_client.post(
        f"/workspaces/{workspace['id']}/memos/{memo['id']}/versions/{version_id}/approve"
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    # Approved records are immutable (CONVENTIONS.md rule 2) — re-running
    # analysis after a profile edit must not mutate this version; it
    # must branch a new one with the recomputed numbers and a diff.
    _set_profile_field(client, workspace["id"], "scale.employee_count", 900)
    rerun = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert rerun.status_code == 201, rerun.text

    memo_after = client.get(f"/workspaces/{workspace['id']}/memos/{memo['id']}")
    assert memo_after.status_code == 200, memo_after.text
    versions = memo_after.json()["versions"]
    assert len(versions) == 2

    approved_version = versions[0]
    assert approved_version["id"] == version_id
    assert approved_version["status"] == "approved"
    approved_obligation = next(
        o
        for o in approved_version["content"]["obligations"]
        if o["predicate_id"] == str(predicate.id)
    )
    assert approved_obligation["impact_likely"] == str(5000 + 40 * 500)

    new_version = versions[1]
    assert new_version["version"] == 2
    assert new_version["status"] == "draft"
    new_obligation = next(
        o for o in new_version["content"]["obligations"] if o["predicate_id"] == str(predicate.id)
    )
    assert new_obligation["impact_likely"] == str(5000 + 40 * 900)
    assert new_version["content"]["change_note"]
    assert new_version["content"]["superseded_version"] == 1


def test_rerun_with_no_existing_memo_does_not_require_an_ai_provider(
    client_as, make_user, db_session
):
    """The overwhelmingly common path — a workspace's first analysis, or
    any re-run before a memo has ever been created — must not touch the
    composition/diff-note providers at all, since neither fixture is
    installed in this test and the real providers fail closed without
    PROVISION_ANTHROPIC_API_KEY. A regression here would 502 on every
    ordinary analysis run, not just re-runs with a memo to sync."""
    owner = make_user()
    client = client_as(owner)
    workspace, obligation, predicate = _setup_workspace_with_bound_obligation(
        client, db_session, make_user
    )

    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)
    first = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert first.status_code == 201, first.text

    _set_profile_field(client, workspace["id"], "scale.employee_count", 900)
    second = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert second.status_code == 201, second.text

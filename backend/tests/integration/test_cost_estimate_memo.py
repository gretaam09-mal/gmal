"""Verifies P-COST-ESTIMATE end to end over real HTTP: a binding
obligation with no expert-authored CostTemplate gets a company-specific
AI cost estimate (with a rationale) instead of being silently dropped
from the memo, the memo's real API response actually carries it labelled
as such (cost_source="ai_estimate"), and an expert cost template — once
attached — overrides it on the next re-run, exactly as
CONVENTIONS.md rule 1's narrow cost-estimation exception requires.
"""

import uuid

from services.composition.schemas import ComposedMemoProse
from services.cost_estimate.schemas import CostEstimate
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


def _fixture_cost_estimate() -> CostEstimate:
    return CostEstimate.model_validate(
        {
            "cost_drivers": [
                {
                    "driver": "Compliance headcount",
                    "detail": "One FTE data protection officer at this headcount.",
                },
                {
                    "driver": "External legal advice",
                    "detail": "Drafting the DPO appointment and reporting lines.",
                },
            ],
            "assumptions": ["Assumes no existing DPO in post."],
            "best": "15000",
            "likely": "25000",
            "worst": "40000",
            "rationale": (
                "Scaled a headcount-based staffing driver to the company's 500 employees, "
                "plus a fixed external-advice component."
            ),
        }
    )


def test_binding_obligation_without_a_cost_template_gets_an_ai_estimate_with_rationale(
    client_as, make_user, db_session, composition_provider_fixture, cost_estimate_provider_fixture
):
    """PART 1's core acceptance test: a bound obligation + a profile ->
    the real /memos response carries a company-specific AI estimate,
    clearly labelled, with the rationale the memo UI displays next to
    the numbers — not the deterministic engine path, since deliberately
    no CostTemplate is attached here."""
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)

    obligation, predicate = _approved_predicate_bound_to_new_obligation(
        db_session,
        make_user,
        expression={"field": "footprint.processes_personal_data", "equals": True},
    )
    # Deliberately no attach_cost_template() call — this obligation binds
    # with no expert-authored cost basis at all.

    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)
    _set_profile_field(client, workspace["id"], "scale.employee_count", 500)
    _set_profile_field(client, workspace["id"], "activity.sector", "Asset management")

    analysis = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert analysis.status_code == 201, analysis.text
    # The exposure list itself already carries the item — confirms this
    # obligation isn't silently dropped even before a memo exists.
    item = next(i for i in analysis.json()["items"] if i["predicate_id"] == str(predicate.id))
    assert item["outcome"] == "binds"

    cost_estimate_provider_fixture.register(str(predicate.id), _fixture_cost_estimate())
    composition_provider_fixture.register(str(predicate.id), _memo_prose(str(predicate.id)))

    memo_resp = client.post(
        f"/workspaces/{workspace['id']}/memos",
        json={"analysis_id": analysis.json()["id"], "title": "Project Falcon — Impact Memo"},
    )
    assert memo_resp.status_code == 201, memo_resp.text
    memo = memo_resp.json()
    version = memo["versions"][0]
    obligation_entry = next(
        o for o in version["content"]["obligations"] if o["predicate_id"] == str(predicate.id)
    )

    # The memo displays it, clearly labelled, with the rationale — not a
    # bare figure.
    assert obligation_entry["cost_source"] == "ai_estimate"
    assert obligation_entry["cost_rationale"] == _fixture_cost_estimate().rationale
    assert obligation_entry["cost_assumptions"] == ["Assumes no existing DPO in post."]
    assert obligation_entry["cost_drivers"] == [
        {
            "driver": "Compliance headcount",
            "detail": "One FTE data protection officer at this headcount.",
        },
        {
            "driver": "External legal advice",
            "detail": "Drafting the DPO appointment and reporting lines.",
        },
    ]
    assert obligation_entry["impact_low"] == "15000"
    assert obligation_entry["impact_likely"] == "25000"
    assert obligation_entry["impact_high"] == "40000"
    # 0% discount rate by default -> present value equals the undiscounted
    # likely figure, computed by engine/impact exactly like a
    # template-derived obligation's would be.
    assert obligation_entry["present_value"] == "25000.00000000"
    assert version["content"]["headline"]["likely"] == "25000"


def test_expert_cost_template_overrides_the_ai_estimate_on_the_next_rerun(
    client_as, make_user, db_session, composition_provider_fixture, cost_estimate_provider_fixture
):
    """ "If an expert cost template is attached, it overrides the AI
    estimate" — verified end to end: create a memo while the obligation
    has only an AI estimate, then have an expert attach a real
    CostTemplate and re-run; the resync must switch cost_source to
    expert_template and use the formula's numbers, not the AI's."""
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client)

    obligation, predicate = _approved_predicate_bound_to_new_obligation(
        db_session,
        make_user,
        expression={"field": "footprint.processes_personal_data", "equals": True},
    )
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)
    _set_profile_field(client, workspace["id"], "scale.employee_count", 500)

    analysis = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert analysis.status_code == 201, analysis.text

    cost_estimate_provider_fixture.register(str(predicate.id), _fixture_cost_estimate())
    composition_provider_fixture.register(str(predicate.id), _memo_prose(str(predicate.id)))

    memo_resp = client.post(
        f"/workspaces/{workspace['id']}/memos",
        json={"analysis_id": analysis.json()["id"], "title": "Project Falcon — Impact Memo"},
    )
    assert memo_resp.status_code == 201, memo_resp.text
    memo = memo_resp.json()
    first_obligation = next(
        o
        for o in memo["versions"][0]["content"]["obligations"]
        if o["predicate_id"] == str(predicate.id)
    )
    assert first_obligation["cost_source"] == "ai_estimate"

    # An expert now attaches a real cost template for this obligation.
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

    rerun = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert rerun.status_code == 201, rerun.text

    memo_after = client.get(f"/workspaces/{workspace['id']}/memos/{memo['id']}")
    assert memo_after.status_code == 200, memo_after.text
    updated_obligation = next(
        o
        for o in memo_after.json()["versions"][0]["content"]["obligations"]
        if o["predicate_id"] == str(predicate.id)
    )
    assert updated_obligation["cost_source"] == "expert_template"
    assert updated_obligation["cost_rationale"] is None
    assert updated_obligation["impact_likely"] == str(5000 + 40 * 500)

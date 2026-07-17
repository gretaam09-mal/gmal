import io
import uuid

from docx import Document

from db.models import AuditEvent, MemoVersion, Report
from db.session import set_rls_context
from services.composition.fixture_provider import FixtureCompositionProvider
from services.composition.schemas import ComposedMemoProse
from services.cost_estimate.fixture_provider import FixtureCostEstimateProvider
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
from services.memo import approve_memo, create_memo_from_analysis, submit_for_review

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


def _seeded_approved_memo(client_as, make_user, db_session, *, title):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client, codename=title)
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)
    _set_profile_field(client, workspace["id"], "scale.employee_count", 500)

    version = ingest_instrument(
        db_session,
        title=f"{title} Act",
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
        db_session, clause=clause, instrument_title=f"{title} Act", provider=provider
    )
    staff = make_user()
    approve_obligation(db_session, obligation=obligation, approved_by_user_id=staff.id)
    predicate = create_predicate(
        db_session,
        obligation=obligation,
        predicate_key="processes_personal_data",
        expression={"field": "footprint.processes_personal_data", "equals": True},
    )
    approve_predicate(db_session, predicate=predicate, approved_by_user_id=staff.id)
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

    analysis_resp = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert analysis_resp.status_code == 201, analysis_resp.text
    set_rls_context(db_session, workspace["tenant_id"], workspace["id"])
    from db.models import Analysis

    analysis = db_session.get(Analysis, uuid.UUID(analysis_resp.json()["id"]))

    composition_provider = FixtureCompositionProvider()
    composition_provider.register(
        str(predicate.id),
        ComposedMemoProse.model_validate(
            {
                "headline_summary": "Bounded exposure.",
                "obligations": [
                    {
                        "predicate_id": str(predicate.id),
                        "what_it_requires": "Appoint a data protection officer.",
                        "why_it_applies": "The target processes personal data at scale.",
                    }
                ],
                "excluded_summary": "Nothing excluded.",
            }
        ),
    )
    memo = create_memo_from_analysis(
        db_session,
        analysis=analysis,
        tenant_id=uuid.UUID(workspace["tenant_id"]),
        workspace_id=uuid.UUID(workspace["id"]),
        title=f"{title} — Impact Memo",
        created_by_user_id=owner.id,
        composition_provider=composition_provider,
        cost_estimate_provider=lambda: FixtureCostEstimateProvider(),
    )
    db_session.commit()

    memo_version = db_session.query(MemoVersion).filter(MemoVersion.memo_id == memo.id).one()
    submit_for_review(memo_version)
    db_session.commit()
    reviewer = make_user()
    approve_memo(
        db_session,
        memo_version=memo_version,
        approved_by_user_id=reviewer.id,
        panel_firm="Outside Counsel LLP",
    )
    db_session.commit()
    return client, workspace, memo, memo_version


def test_print_preview_returns_html_matching_approved_content(client_as, make_user, db_session):
    client, workspace, memo, memo_version = _seeded_approved_memo(
        client_as, make_user, db_session, title="project-falcon"
    )

    resp = client.get(
        f"/workspaces/{workspace['id']}/memos/{memo.id}/versions/{memo_version.id}/print-preview"
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/html")
    assert "Appoint a data protection officer." in resp.text
    assert "project-falcon Act" in resp.text
    assert "Outside Counsel LLP" in resp.text


def test_export_pdf_returns_valid_pdf_and_records_report(client_as, make_user, db_session):
    client, workspace, memo, memo_version = _seeded_approved_memo(
        client_as, make_user, db_session, title="project-condor"
    )

    resp = client.get(
        f"/workspaces/{workspace['id']}/memos/{memo.id}/versions/{memo_version.id}/export.pdf"
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF-")

    set_rls_context(db_session, workspace["tenant_id"], workspace["id"])
    reports = db_session.query(Report).filter(Report.memo_version_id == memo_version.id).all()
    assert len(reports) == 1
    assert reports[0].report_type == "pdf"

    audit_events = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.entity_id == memo_version.id, AuditEvent.action == "memo.exported.pdf")
        .all()
    )
    assert len(audit_events) == 1


def test_export_docx_returns_valid_docx_and_records_report(client_as, make_user, db_session):
    client, workspace, memo, memo_version = _seeded_approved_memo(
        client_as, make_user, db_session, title="project-kestrel"
    )

    resp = client.get(
        f"/workspaces/{workspace['id']}/memos/{memo.id}/versions/{memo_version.id}/export.docx"
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert resp.content.startswith(b"PK")

    # F8 success criterion: the export matches the approved on-screen
    # version exactly — same obligation prose, same headline grade.
    document = Document(io.BytesIO(resp.content))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "Appoint a data protection officer." in text
    assert f"Confidence grade: {memo_version.content['confidence_grade']}" in text

    set_rls_context(db_session, workspace["tenant_id"], workspace["id"])
    reports = db_session.query(Report).filter(Report.memo_version_id == memo_version.id).all()
    assert len(reports) == 1
    assert reports[0].report_type == "docx"


def test_export_routes_404_for_memo_in_another_workspace(client_as, make_user, db_session):
    client, workspace, memo, memo_version = _seeded_approved_memo(
        client_as, make_user, db_session, title="project-osprey"
    )
    other_owner = make_user()
    other_client = client_as(other_owner)
    other_workspace = _create_tenant_and_workspace(other_client, codename="project-heron")

    resp = other_client.get(
        f"/workspaces/{other_workspace['id']}/memos/{memo.id}"
        f"/versions/{memo_version.id}/export.pdf"
    )

    assert resp.status_code == 404

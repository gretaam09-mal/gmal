import uuid

from db.models import (
    CostTemplate,
    Memo,
    MemoVersion,
    Obligation,
    ReviewCorrection,
    Tenant,
    Workspace,
)
from db.models.enums import MemoStatus
from db.session import set_rls_context
from services.extraction import ExtractedObligation, FixtureExtractionProvider
from services.instrument_onboarding import (
    approve_obligation,
    attach_cost_template,
    extract_obligation,
    ingest_instrument,
    list_clauses,
)
from services.review import record_cost_template_correction, record_obligation_correction

_RAW_TEXT = (
    "1. A firm that processes personal data at scale must appoint a data protection officer."
)


def _approved_obligation(db_session, make_user):
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
            "confidence": 60,
        }
    )
    provider = FixtureExtractionProvider({clause.clause_ref: extracted})
    obligation = extract_obligation(
        db_session, clause=clause, instrument_title="Test Data Protection Act", provider=provider
    )
    staff = make_user()
    approve_obligation(db_session, obligation=obligation, approved_by_user_id=staff.id)
    db_session.commit()
    return obligation


def _bare_memo_version(db_session, make_user):
    """A minimal, real Memo + MemoVersion — record_*_correction only
    reads tenant_id/workspace_id/id off it, but ReviewCorrection has a
    real FK to memo_versions, so a stand-in object won't satisfy it."""
    owner = make_user()
    tenant = Tenant(name="Fund A", slug=f"fund-{uuid.uuid4().hex[:8]}", created_by_user_id=owner.id)
    db_session.add(tenant)
    db_session.flush()
    set_rls_context(db_session, tenant.id, None)
    workspace = Workspace(
        tenant_id=tenant.id, codename="project-falcon", created_by_user_id=owner.id
    )
    db_session.add(workspace)
    db_session.flush()
    set_rls_context(db_session, tenant.id, workspace.id)
    memo = Memo(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        title="Test memo",
        created_by_user_id=owner.id,
    )
    db_session.add(memo)
    db_session.flush()
    memo_version = MemoVersion(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        memo_id=memo.id,
        version=1,
        content={},
        status=MemoStatus.IN_REVIEW,
        created_by_user_id=owner.id,
    )
    db_session.add(memo_version)
    db_session.flush()
    db_session.commit()
    return memo_version


def test_obligation_correction_creates_a_new_version_and_a_provenance_record(
    db_session, make_user
):
    obligation = _approved_obligation(db_session, make_user)
    reviewer = make_user()
    memo_version = _bare_memo_version(db_session, make_user)

    corrected, correction = record_obligation_correction(
        db_session,
        memo_version=memo_version,
        obligation=obligation,
        summary="Appoint a data protection officer within 30 days.",
        obligation_type="appointment",
        fields=obligation.fields,
        confidence=95,
        corrected_by_user_id=reviewer.id,
        note="The original extraction missed the 30-day deadline.",
    )
    db_session.commit()

    assert corrected.id != obligation.id
    assert corrected.summary == "Appoint a data protection officer within 30 days."
    assert corrected.approved is False  # a correction is unapproved until re-reviewed
    assert corrected.clause_id == obligation.clause_id

    db_session.refresh(obligation)
    assert obligation.valid_to is not None  # the old version is closed, not deleted

    stored = db_session.get(ReviewCorrection, correction.id)
    assert stored.obligation_id == corrected.id
    assert stored.cost_template_id is None
    assert stored.corrected_by_user_id == reviewer.id
    assert stored.note == "The original extraction missed the 30-day deadline."

    # the correction improves the *next* memo built from this obligation
    # too, not just the one being reviewed — confirm the new row is what
    # a fresh query for the obligation's current version returns.
    current = (
        db_session.query(Obligation)
        .filter(Obligation.clause_id == obligation.clause_id, Obligation.valid_to.is_(None))
        .one()
    )
    assert current.id == corrected.id


def test_cost_template_correction_versions_and_records_provenance(db_session, make_user):
    obligation = _approved_obligation(db_session, make_user)
    original_template = attach_cost_template(
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

    reviewer = make_user()
    memo_version = _bare_memo_version(db_session, make_user)

    corrected, correction = record_cost_template_correction(
        db_session,
        memo_version=memo_version,
        obligation=obligation,
        name="DPO cost (revised)",
        drivers=[{"key": "scale.employee_count", "label": "Employee count"}],
        formula={"base": 8000, "terms": [{"driver": "scale.employee_count", "rate": 45}]},
        currency="GBP",
        source_basis="vendor quote",
        maturity_tier="quoted",
        corrected_by_user_id=reviewer.id,
        note="Vendor quote came in higher than the initial estimate.",
    )
    db_session.commit()

    assert corrected.id != original_template.id
    assert corrected.formula["base"] == 8000

    db_session.refresh(original_template)
    assert original_template.valid_to is not None

    stored = db_session.get(ReviewCorrection, correction.id)
    assert stored.cost_template_id == corrected.id
    assert stored.obligation_id is None

    current = (
        db_session.query(CostTemplate)
        .filter(CostTemplate.obligation_id == obligation.id, CostTemplate.valid_to.is_(None))
        .one()
    )
    assert current.id == corrected.id

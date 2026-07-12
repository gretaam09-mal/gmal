import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from db.models import Analysis, Assumption, MemoVersion
from db.models.enums import MemoStatus
from db.session import set_rls_context
from services.composition.fixture_provider import FixtureCompositionProvider
from services.composition.schemas import ComposedMemoProse
from services.diff_note.fixture_provider import FixtureDiffNoteProvider
from services.diff_note.schemas import ComposedDiffNote
from services.diff_note.validator import validate_diff_note
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
from services.memo import (
    MemoLockedError,
    approve_memo,
    create_memo_from_analysis,
    create_new_version_from_approved,
    override_assumption_and_recompute,
    submit_for_review,
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


def _run_analysis(client, workspace_id):
    resp = client.post(f"/workspaces/{workspace_id}/analyses", json={})
    assert resp.status_code == 201, resp.text
    return resp.json()


class _StubDiffNoteProvider:
    """A test-only provider that validates the note against whatever
    changes it's actually given, sidestepping the need to predict the
    fixture-registration key up front (which depends on a UUID)."""

    def __init__(self, note: ComposedDiffNote) -> None:
        self._note = note

    def summarise(self, changes):
        validate_diff_note(self._note, changes)
        return self._note


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


def _setup_memo(client_as, make_user, db_session):
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

    analysis_json = _run_analysis(client, workspace["id"])
    set_rls_context(db_session, workspace["tenant_id"], workspace["id"])
    analysis = db_session.get(Analysis, uuid.UUID(analysis_json["id"]))

    composition_provider = FixtureCompositionProvider()
    composition_provider.register(str(predicate.id), _memo_prose(str(predicate.id)))

    memo = create_memo_from_analysis(
        db_session,
        analysis=analysis,
        tenant_id=uuid.UUID(workspace["tenant_id"]),
        workspace_id=uuid.UUID(workspace["id"]),
        title="Project Falcon — Impact Memo",
        created_by_user_id=owner.id,
        composition_provider=composition_provider,
    )
    db_session.commit()
    return workspace, owner, predicate, memo


def test_create_memo_from_analysis_populates_content_and_assumptions(
    client_as, make_user, db_session
):
    _workspace, _owner, predicate, memo = _setup_memo(client_as, make_user, db_session)

    version = (
        db_session.query(MemoVersion).filter(MemoVersion.memo_id == memo.id).one()
    )
    assert version.status == MemoStatus.DRAFT
    assert version.version == 1

    content = version.content
    assert Decimal(content["headline"]["likely"]) == Decimal(5000 + 40 * 500)
    obligation_entry = next(
        o for o in content["obligations"] if o["predicate_id"] == str(predicate.id)
    )
    assert obligation_entry["what_it_requires"] == "Appoint a data protection officer."
    assert content["confidence_grade"] in ("A", "B", "C", "D")

    assumptions = (
        db_session.query(Assumption).filter(Assumption.memo_version_id == version.id).all()
    )
    keys = {a.key for a in assumptions}
    assert "discount_rate_pct" in keys
    assert f"driver:{predicate.id}:scale.employee_count" in keys


def test_override_assumption_recomputes_and_produces_a_diff_note(
    client_as, make_user, db_session
):
    _workspace, _owner, predicate, memo = _setup_memo(client_as, make_user, db_session)
    version = db_session.query(MemoVersion).filter(MemoVersion.memo_id == memo.id).one()
    driver_key = f"driver:{predicate.id}:scale.employee_count"
    assumption = (
        db_session.query(Assumption)
        .filter(Assumption.memo_version_id == version.id, Assumption.key == driver_key)
        .one()
    )
    old_likely = Decimal(version.content["headline"]["likely"])

    diff_note_provider = _StubDiffNoteProvider(
        ComposedDiffNote.model_validate(
            {"change_note": "The employee count assumption was revised from 500 to 1,000."}
        )
    )

    updated_version, diff_note, changes = override_assumption_and_recompute(
        db_session,
        memo_version=version,
        assumption=assumption,
        new_value={"value": "1000"},
        note="Revised headcount from latest management accounts.",
        diff_note_provider=diff_note_provider,
    )
    db_session.commit()

    new_likely = Decimal(updated_version.content["headline"]["likely"])
    assert new_likely == Decimal(5000 + 40 * 1000)
    assert new_likely > old_likely
    assert any(c.field == "headline_likely" for c in changes)
    assert "employee count" in diff_note.change_note.lower()

    # prose is carried forward untouched by a pure numeric override
    obligation_entry = next(
        o for o in updated_version.content["obligations"] if o["predicate_id"] == str(predicate.id)
    )
    assert obligation_entry["what_it_requires"] == "Appoint a data protection officer."


def test_full_lifecycle_draft_to_in_review_to_approved(client_as, make_user, db_session):
    _workspace, owner, _predicate, memo = _setup_memo(client_as, make_user, db_session)
    version = db_session.query(MemoVersion).filter(MemoVersion.memo_id == memo.id).one()

    submit_for_review(version)
    assert version.status == MemoStatus.IN_REVIEW
    db_session.commit()

    approve_memo(db_session, memo_version=version, approved_by_user_id=owner.id)
    db_session.commit()

    db_session.refresh(version)
    assert version.status == MemoStatus.APPROVED
    assert version.approved_at is not None
    assert version.approved_by_user_id == owner.id


def test_approved_memo_version_cannot_be_overridden_at_the_service_layer(
    client_as, make_user, db_session
):
    _workspace, owner, predicate, memo = _setup_memo(client_as, make_user, db_session)
    version = db_session.query(MemoVersion).filter(MemoVersion.memo_id == memo.id).one()
    submit_for_review(version)
    db_session.commit()
    approve_memo(db_session, memo_version=version, approved_by_user_id=owner.id)
    db_session.commit()

    driver_key = f"driver:{predicate.id}:scale.employee_count"
    assumption = (
        db_session.query(Assumption)
        .filter(Assumption.memo_version_id == version.id, Assumption.key == driver_key)
        .one()
    )
    with pytest.raises(MemoLockedError):
        override_assumption_and_recompute(
            db_session,
            memo_version=version,
            assumption=assumption,
            new_value={"value": "9999"},
            note=None,
            diff_note_provider=FixtureDiffNoteProvider(),
        )


def test_approved_memo_version_is_immutable_at_the_db_layer(client_as, make_user, db_session):
    """Defense in depth: even bypassing the service layer entirely and
    issuing a raw UPDATE against an approved memo_versions row, the DB
    trigger (migration a3f1c9d47b2e) rejects it."""
    _workspace, owner, _predicate, memo = _setup_memo(client_as, make_user, db_session)
    version = db_session.query(MemoVersion).filter(MemoVersion.memo_id == memo.id).one()
    submit_for_review(version)
    db_session.commit()
    approve_memo(db_session, memo_version=version, approved_by_user_id=owner.id)
    db_session.commit()

    with pytest.raises(Exception, match="immutable"):
        db_session.execute(
            text("UPDATE memo_versions SET content = '{}' WHERE id = :id"), {"id": version.id}
        )
        db_session.commit()
    db_session.rollback()


def test_change_after_approval_creates_a_new_version_not_a_mutation(
    client_as, make_user, db_session
):
    _workspace, owner, _predicate, memo = _setup_memo(client_as, make_user, db_session)
    version = db_session.query(MemoVersion).filter(MemoVersion.memo_id == memo.id).one()
    submit_for_review(version)
    db_session.commit()
    approve_memo(db_session, memo_version=version, approved_by_user_id=owner.id)
    db_session.commit()

    new_version = create_new_version_from_approved(
        db_session,
        memo=memo,
        base_version=version,
        change_note="Recomputed after updated management accounts.",
        created_by_user_id=owner.id,
    )
    db_session.commit()

    assert new_version.version == 2
    assert new_version.status == MemoStatus.DRAFT
    assert new_version.content["change_note"] == "Recomputed after updated management accounts."
    assert new_version.content["superseded_version"] == 1

    new_assumptions = (
        db_session.query(Assumption).filter(Assumption.memo_version_id == new_version.id).all()
    )
    old_assumptions = (
        db_session.query(Assumption).filter(Assumption.memo_version_id == version.id).all()
    )
    assert len(new_assumptions) == len(old_assumptions)

import uuid

from db.models import CuratedSource, InstrumentVersion, MemoInputChangeFlag, MemoVersion
from db.models.enums import SweepRunStatus
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
from services.sources.fetcher import FixtureSourceFetcher
from services.sources.sweep import run_sweep

_ORIGINAL_TEXT = (
    "1. A firm that processes personal data at scale must appoint a data protection officer."
)
_AMENDED_TEXT = (
    "1. A firm that processes personal data at scale must appoint a data protection officer.\n\n"
    "2. The data protection officer must report annually to the board."
)
_SOURCE_URL = "fixture://test-data-protection-source"


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
        source_url=_SOURCE_URL,
        raw_text=_ORIGINAL_TEXT,
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
    approve_memo(db_session, memo_version=memo_version, approved_by_user_id=reviewer.id)
    db_session.commit()
    return workspace, memo, memo_version, version.instrument_id


def _register_curated_source(db_session, *, instrument_id):
    source = CuratedSource(
        key=f"test-source-{uuid.uuid4().hex[:8]}",
        name="Test Data Protection Source",
        url=_SOURCE_URL,
        instrument_id=instrument_id,
        last_content_hash=None,
        last_swept_at=None,
    )
    db_session.add(source)
    db_session.commit()
    return source


def test_sweep_detects_no_change_when_content_is_identical(client_as, make_user, db_session):
    _workspace, _memo, _memo_version, instrument_id = _seeded_approved_memo(
        client_as, make_user, db_session, title="project-falcon"
    )
    _register_curated_source(db_session, instrument_id=instrument_id)
    fetcher = FixtureSourceFetcher({_SOURCE_URL: _ORIGINAL_TEXT})

    sweep_run, changes = run_sweep(db_session, fetcher)
    db_session.commit()

    assert sweep_run.status == SweepRunStatus.COMPLETE
    assert changes == []
    assert sweep_run.summary["memos_flagged"] == 0


def test_sweep_versions_instrument_and_flags_affected_memo(client_as, make_user, db_session):
    workspace, memo, memo_version, instrument_id = _seeded_approved_memo(
        client_as, make_user, db_session, title="project-condor"
    )
    _register_curated_source(db_session, instrument_id=instrument_id)
    fetcher = FixtureSourceFetcher({_SOURCE_URL: _AMENDED_TEXT})

    sweep_run, changes = run_sweep(db_session, fetcher)
    db_session.commit()

    assert sweep_run.status == SweepRunStatus.COMPLETE
    assert len(changes) == 1
    change = changes[0]
    assert change.instrument_id == instrument_id
    assert len(change.flagged_memos) == 1
    assert change.flagged_memos[0].memo_id == memo.id

    old_version = db_session.get(InstrumentVersion, change.old_instrument_version_id)
    new_version = db_session.get(InstrumentVersion, change.new_instrument_version_id)
    assert old_version.valid_to is not None
    assert new_version.valid_to is None
    assert new_version.raw_text == _AMENDED_TEXT

    set_rls_context(db_session, workspace["tenant_id"], workspace["id"])
    flags = (
        db_session.query(MemoInputChangeFlag)
        .filter(MemoInputChangeFlag.memo_version_id == memo_version.id)
        .all()
    )
    assert len(flags) == 1
    assert flags[0].instrument_version_id == old_version.id


def test_sweep_rerun_is_idempotent_after_a_detected_change(client_as, make_user, db_session):
    _workspace, memo, _memo_version, instrument_id = _seeded_approved_memo(
        client_as, make_user, db_session, title="project-kestrel"
    )
    source = _register_curated_source(db_session, instrument_id=instrument_id)
    fetcher = FixtureSourceFetcher({_SOURCE_URL: _AMENDED_TEXT})

    _first_run, first_changes = run_sweep(db_session, fetcher)
    db_session.commit()
    assert len(first_changes) == 1

    db_session.refresh(source)
    second_run, second_changes = run_sweep(db_session, fetcher)
    db_session.commit()

    assert second_run.status == SweepRunStatus.COMPLETE
    assert second_changes == []

    instruments = (
        db_session.query(InstrumentVersion)
        .filter(InstrumentVersion.instrument_id == instrument_id)
        .all()
    )
    assert len(instruments) == 2  # original + the one amended version, not a third
    _ = memo

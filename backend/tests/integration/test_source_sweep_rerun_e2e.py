"""F9 acceptance test: a simulated source change produces the flag, the
email, and a working re-run path, end to end — from the original
approved memo, through the sweep, through a human onboarding the new
instrument version's clause (the existing F3 workbench flow), to a
fresh memo whose content reflects the updated regulation.
"""

import uuid

from api.deps import get_composition_provider
from api.main import app
from db.models import CuratedSource, InstrumentVersion, MemoInputChangeFlag
from db.session import set_rls_context
from services.composition.fixture_provider import FixtureCompositionProvider
from services.composition.schemas import ComposedMemoProse, ComposedObligationProse
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
from services.notifications.email import StubEmailProvider
from services.sources.fetcher import FixtureSourceFetcher
from services.sources.notify import notify_affected_memos
from services.sources.sweep import run_sweep

_ORIGINAL_TEXT = (
    "1. A firm that processes personal data at scale must appoint a data protection officer."
)
_AMENDED_TEXT = (
    "1. A firm that processes personal data at scale must appoint a data protection officer.\n\n"
    "2. The data protection officer must report annually to the board."
)
_SOURCE_URL = "fixture://rerun-e2e-source"


def _create_tenant_and_workspace(client, codename):
    slug = f"fund-{uuid.uuid4().hex[:8]}"
    tenant = client.post("/tenants", json={"name": "Fund A", "slug": slug})
    assert tenant.status_code == 201, tenant.text
    workspace = client.post(
        f"/tenants/{tenant.json()['id']}/workspaces", json={"codename": codename}
    )
    assert workspace.status_code == 201, workspace.text
    return workspace.json()


def _set_profile_field(client, workspace_id, key, value):
    resp = client.put(
        f"/workspaces/{workspace_id}/profile",
        json={"fields": [{"key": key, "value": value, "source": "user"}]},
    )
    assert resp.status_code == 200, resp.text


def _extract_and_approve(db_session, make_user, *, clause, instrument_title, summary, when):
    extracted = ExtractedObligation.model_validate(
        {
            "summary": summary,
            "obligation_type": "reporting",
            "who": {
                "value": "firms processing personal data at scale",
                "clause_ref": clause.clause_ref,
                "confidence": 90,
            },
            "what": {"value": summary, "clause_ref": clause.clause_ref, "confidence": 95},
            "when": {"value": when, "clause_ref": clause.clause_ref, "confidence": 50},
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
        db_session, clause=clause, instrument_title=instrument_title, provider=provider
    )
    staff = make_user()
    approve_obligation(db_session, obligation=obligation, approved_by_user_id=staff.id)
    predicate = create_predicate(
        db_session,
        obligation=obligation,
        predicate_key=f"processes_personal_data_{uuid.uuid4().hex[:6]}",
        expression={"field": "footprint.processes_personal_data", "equals": True},
    )
    approve_predicate(db_session, predicate=predicate, approved_by_user_id=staff.id)
    attach_cost_template(
        db_session,
        obligation=obligation,
        name=f"{summary} cost",
        drivers=[{"key": "scale.employee_count", "label": "Employee count"}],
        formula={"base": 1000, "terms": [{"driver": "scale.employee_count", "rate": 10}]},
        currency="GBP",
        source_basis="expert estimate",
        maturity_tier="rough",
    )
    return predicate


class _EchoCompositionProvider:
    """Generic across however many obligations bind — echoes each
    obligation's own summary, sidestepping FixtureCompositionProvider's
    exact-key-per-predicate-combination lookup, which the memo re-run
    step can't predict the order of."""

    def compose(self, context) -> ComposedMemoProse:
        return ComposedMemoProse(
            headline_summary="Bounded exposure, updated.",
            obligations=[
                ComposedObligationProse(
                    predicate_id=o.predicate_id,
                    what_it_requires=o.obligation_summary,
                    why_it_applies="The target processes personal data at scale.",
                )
                for o in context.binding_obligations
            ],
            excluded_summary="Nothing excluded.",
        )


def test_sweep_flag_email_and_rerun_path_end_to_end(
    client_as, make_user, db_session, diff_note_provider_fixture
):
    owner = make_user()
    client = client_as(owner)
    workspace = _create_tenant_and_workspace(client, codename="project-heron")
    _set_profile_field(client, workspace["id"], "footprint.processes_personal_data", True)
    _set_profile_field(client, workspace["id"], "scale.employee_count", 500)

    instrument_title = "Heron Data Protection Act"
    instrument_version = ingest_instrument(
        db_session,
        title=instrument_title,
        jurisdiction="UK",
        kind="Act",
        citation=None,
        version_label="v1",
        source_url=_SOURCE_URL,
        raw_text=_ORIGINAL_TEXT,
    )
    clause = list_clauses(db_session, instrument_version.id)[0]
    predicate = _extract_and_approve(
        db_session,
        make_user,
        clause=clause,
        instrument_title=instrument_title,
        summary="Appoint a data protection officer.",
        when="2026-01-01",
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
        title="Project Heron — Impact Memo",
        created_by_user_id=owner.id,
        composition_provider=composition_provider,
    )
    from db.models import MemoVersion

    memo_version = db_session.query(MemoVersion).filter(MemoVersion.memo_id == memo.id).one()
    submit_for_review(memo_version)
    db_session.commit()
    reviewer = make_user()
    approve_memo(db_session, memo_version=memo_version, approved_by_user_id=reviewer.id)
    db_session.commit()

    # --- the source changes ------------------------------------------------
    source = CuratedSource(
        key=f"heron-source-{uuid.uuid4().hex[:8]}",
        name="Heron Data Protection Source",
        url=_SOURCE_URL,
        instrument_id=instrument_version.instrument_id,
    )
    db_session.add(source)
    db_session.commit()
    fetcher = FixtureSourceFetcher({_SOURCE_URL: _AMENDED_TEXT})

    sweep_run, changes = run_sweep(db_session, fetcher)
    db_session.commit()
    assert len(changes) == 1
    assert len(changes[0].flagged_memos) == 1

    email_provider = StubEmailProvider()
    messages = notify_affected_memos(db_session, email_provider, changes)
    db_session.commit()
    assert len(messages) == 1
    assert "Project Heron — Impact Memo" in messages[0].body
    assert messages[0].to == owner.email

    set_rls_context(db_session, workspace["tenant_id"], workspace["id"])
    flags = (
        db_session.query(MemoInputChangeFlag)
        .filter(MemoInputChangeFlag.memo_version_id == memo_version.id)
        .all()
    )
    assert len(flags) == 1

    # --- re-run path: a human reviews the new clause, then a fresh
    # analysis + memo naturally picks up the updated regulation --------
    new_version = db_session.get(InstrumentVersion, changes[0].new_instrument_version_id)
    new_clauses = list_clauses(db_session, new_version.id)
    reporting_clause = next(c for c in new_clauses if "report annually" in c.text)
    _extract_and_approve(
        db_session,
        make_user,
        clause=reporting_clause,
        instrument_title=instrument_title,
        summary="Report annually to the board.",
        when="2027-01-01",
    )
    db_session.commit()

    # The re-run itself now also auto-syncs the original approved memo
    # (see services/memo.py::sync_memo_to_latest_analysis) — since it's
    # approved, that branches a new Draft version rather than mutating
    # it. _EchoCompositionProvider (not FixtureCompositionProvider)
    # because the auto-sync's binding-obligation set/order isn't
    # predictable enough here to pre-register an exact fixture key for.
    app.dependency_overrides[get_composition_provider] = lambda: _EchoCompositionProvider()
    try:
        rerun_analysis_resp = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
        assert rerun_analysis_resp.status_code == 201, rerun_analysis_resp.text
    finally:
        app.dependency_overrides.pop(get_composition_provider, None)
    set_rls_context(db_session, workspace["tenant_id"], workspace["id"])
    rerun_analysis = db_session.get(Analysis, uuid.UUID(rerun_analysis_resp.json()["id"]))

    db_session.refresh(memo_version)
    synced_versions = (
        db_session.query(MemoVersion)
        .filter(MemoVersion.memo_id == memo_version.memo_id)
        .order_by(MemoVersion.version)
        .all()
    )
    assert len(synced_versions) == 2
    assert synced_versions[0].id == memo_version.id
    assert synced_versions[0].status.value == "approved"
    assert synced_versions[1].status.value == "draft"
    synced_summaries = {o["obligation_summary"] for o in synced_versions[1].content["obligations"]}
    assert "Appoint a data protection officer." in synced_summaries
    assert "Report annually to the board." in synced_summaries

    rerun_composition_provider = _EchoCompositionProvider()
    rerun_memo = create_memo_from_analysis(
        db_session,
        analysis=rerun_analysis,
        tenant_id=uuid.UUID(workspace["tenant_id"]),
        workspace_id=uuid.UUID(workspace["id"]),
        title="Project Heron — Impact Memo (re-run)",
        created_by_user_id=owner.id,
        composition_provider=rerun_composition_provider,
    )
    rerun_version = db_session.query(MemoVersion).filter(MemoVersion.memo_id == rerun_memo.id).one()

    summaries = {o["obligation_summary"] for o in rerun_version.content["obligations"]}
    assert "Appoint a data protection officer." in summaries
    assert "Report annually to the board." in summaries
    _ = sweep_run

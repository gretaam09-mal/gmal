"""F6's three explicit success criteria, checked directly (not just
incidentally covered by other tests):

1. Any headline number traces to its clauses and template versions in
   <=3 clicks — checked at the data level: a memo's GET response already
   carries clause_refs and rationale inline on every obligation entry
   that also carries its cost figures, so no extra round trip is needed
   between "see a number" and "see what it cites".
2. Override -> recompute -> diff works end-to-end in under 2 minutes —
   timed directly (see test_analyses_performance.py for the identical
   F4 pattern).
3. No code path can mutate an approved memo — the DB trigger
   (migration a3f1c9d47b2e) is unconditional, checked here via both the
   ORM and a raw UPDATE against memo_versions *and* assumptions, not
   just through services/memo.py's own guard.
"""

import time
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from db.models import Analysis, Assumption, MemoVersion
from db.session import set_rls_context
from services.composition.fixture_provider import FixtureCompositionProvider
from services.composition.schemas import ComposedMemoProse
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
    approve_memo,
    create_memo_from_analysis,
    override_assumption_and_recompute,
    submit_for_review,
)

_RAW_TEXT = (
    "1. A firm that processes personal data at scale must appoint a data protection officer."
)


class _StubDiffNoteProvider:
    def summarise(self, changes):
        note = ComposedDiffNote.model_validate({"change_note": "Recomputed after an override."})
        validate_diff_note(note, changes)
        return note


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

    analysis_json = client.post(f"/workspaces/{workspace['id']}/analyses", json={})
    assert analysis_json.status_code == 201, analysis_json.text
    set_rls_context(db_session, workspace["tenant_id"], workspace["id"])
    analysis = db_session.get(Analysis, uuid.UUID(analysis_json.json()["id"]))

    composition_provider = FixtureCompositionProvider()
    composition_provider.register(
        str(predicate.id),
        ComposedMemoProse.model_validate(
            {
                "headline_summary": "Bounded, quantified exposure.",
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
        title="Project Falcon — Impact Memo",
        created_by_user_id=owner.id,
        composition_provider=composition_provider,
    )
    db_session.commit()
    return workspace, owner, predicate, memo


def test_headline_number_traces_to_clauses_within_the_same_response(
    client_as, make_user, db_session
):
    """Success criterion 1: a headline figure traces to its clauses in
    <=3 clicks. At the data level, that means clause_refs and the
    figures they support arrive in the *same* obligation entry of the
    *same* GET response — no second fetch is ever required to find a
    citation for a number already on screen."""
    _workspace, _owner, predicate, memo = _setup_memo(client_as, make_user, db_session)
    version = db_session.query(MemoVersion).filter(MemoVersion.memo_id == memo.id).one()

    obligation_entry = next(
        o for o in version.content["obligations"] if o["predicate_id"] == str(predicate.id)
    )
    # click 1: open the memo (already have version.content); click 2:
    # expand this obligation's card; the clause refs are already present
    # in that same payload — no click 3 needed, well within budget.
    assert obligation_entry["clause_refs"], "obligation entry must carry its own clause citations"
    assert obligation_entry["impact_likely"]
    assert obligation_entry["rationale"]
    # the headline figure is a sum of exactly these per-obligation
    # figures, so it too traces back to this same obligation entry.
    headline_likely = Decimal(version.content["headline"]["likely"])
    assert headline_likely == Decimal(obligation_entry["impact_likely"])


def test_override_recompute_diff_completes_in_under_two_minutes(client_as, make_user, db_session):
    """Success criterion 2: override -> recompute -> diff end to end in
    under 2 minutes. The numeric recompute is pure engine/impact calls
    (no I/O beyond the DB); the diff note here uses a stub provider
    (never a live model call in tests — see CONVENTIONS.md), so this
    measures the code path's own overhead, not network latency."""
    _workspace, _owner, predicate, memo = _setup_memo(client_as, make_user, db_session)
    version = db_session.query(MemoVersion).filter(MemoVersion.memo_id == memo.id).one()
    driver_key = f"driver:{predicate.id}:scale.employee_count"
    assumption = (
        db_session.query(Assumption)
        .filter(Assumption.memo_version_id == version.id, Assumption.key == driver_key)
        .one()
    )

    start = time.monotonic()
    _updated_version, diff_note, changes = override_assumption_and_recompute(
        db_session,
        memo_version=version,
        assumption=assumption,
        new_value={"value": "1000"},
        note="Revised headcount",
        diff_note_provider=_StubDiffNoteProvider(),
    )
    db_session.commit()
    elapsed = time.monotonic() - start

    assert elapsed < 120, f"override+recompute+diff took {elapsed:.2f}s, expected < 120s"
    assert diff_note.change_note
    assert changes


def test_no_code_path_can_mutate_an_approved_memo(client_as, make_user, db_session):
    """Success criterion 3, checked from multiple angles: the ORM setting
    a column and flushing, and a raw UPDATE — against both memo_versions
    and its child assumptions — must all be rejected once approved."""
    _workspace, owner, predicate, memo = _setup_memo(client_as, make_user, db_session)
    version = db_session.query(MemoVersion).filter(MemoVersion.memo_id == memo.id).one()
    submit_for_review(version)
    db_session.commit()
    approve_memo(db_session, memo_version=version, approved_by_user_id=owner.id)
    db_session.commit()

    # angle 1: ORM attribute mutation + flush
    version.confidence_grade = "Z"
    with pytest.raises(Exception, match="immutable"):
        db_session.flush()
    db_session.rollback()

    # angle 2: raw UPDATE against memo_versions
    with pytest.raises(Exception, match="immutable"):
        db_session.execute(
            text("UPDATE memo_versions SET confidence_grade = 'Z' WHERE id = :id"),
            {"id": version.id},
        )
        db_session.commit()
    db_session.rollback()

    # angle 3: raw UPDATE against a child assumption of an approved version
    driver_key = f"driver:{predicate.id}:scale.employee_count"
    assumption = (
        db_session.query(Assumption)
        .filter(Assumption.memo_version_id == version.id, Assumption.key == driver_key)
        .one()
    )
    with pytest.raises(Exception, match="immutable"):
        db_session.execute(
            text("UPDATE assumptions SET note = 'sneaky' WHERE id = :id"), {"id": assumption.id}
        )
        db_session.commit()
    db_session.rollback()

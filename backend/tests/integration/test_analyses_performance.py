"""F4 success criterion: full-set evaluation completes in under 60
seconds. Seeds a large, realistic-scale set of approved obligations/
predicates directly via the service layer (HTTP round-trips would
measure the test client, not the engine) and times run_analysis itself.
"""

import time
import uuid

from db.models import ProfileFieldSource, Tenant, Workspace
from db.session import set_rls_context
from services.analyses import list_analysis_item_views, run_analysis
from services.entity_profile import FieldUpdate, create_profile_version
from services.extraction import ExtractedObligation, FixtureExtractionProvider
from services.instrument_onboarding import (
    approve_obligation,
    approve_predicate,
    create_predicate,
    extract_obligation,
    ingest_instrument,
    list_clauses,
)

_PREDICATE_COUNT = 300


def test_full_set_evaluation_completes_in_under_60_seconds(db_session, make_user):
    owner = make_user()
    tenant = Tenant(
        name="Perf Fund", slug=f"perf-{uuid.uuid4().hex[:8]}", created_by_user_id=owner.id
    )
    db_session.add(tenant)
    db_session.flush()
    set_rls_context(db_session, tenant.id, None)
    workspace = Workspace(
        tenant_id=tenant.id, codename="perf-test", created_by_user_id=owner.id
    )
    db_session.add(workspace)
    db_session.flush()
    set_rls_context(db_session, tenant.id, workspace.id)
    db_session.commit()

    raw_text = "\n\n".join(
        f"{i}. A firm meeting condition {i} must comply." for i in range(1, _PREDICATE_COUNT + 1)
    )
    version = ingest_instrument(
        db_session,
        title="Large Synthetic Instrument",
        jurisdiction="UK",
        kind="Act",
        citation=None,
        version_label="v1",
        source_url=None,
        raw_text=raw_text,
    )
    clauses = list_clauses(db_session, version.id)
    assert len(clauses) == _PREDICATE_COUNT

    for i, clause in enumerate(clauses):
        extracted = ExtractedObligation.model_validate(
            {
                "summary": f"Comply with condition {i}.",
                "obligation_type": "generic",
                "who": {"value": "x", "clause_ref": clause.clause_ref, "confidence": 80},
                "what": {"value": "x", "clause_ref": clause.clause_ref, "confidence": 80},
                "when": {"value": "x", "clause_ref": clause.clause_ref, "confidence": 80},
                "threshold": {"value": "x", "clause_ref": clause.clause_ref, "confidence": 80},
                "enforcer": {"value": "x", "clause_ref": clause.clause_ref, "confidence": 80},
                "confidence": 80,
            }
        )
        provider = FixtureExtractionProvider({clause.clause_ref: extracted})
        obligation = extract_obligation(
            db_session,
            clause=clause,
            instrument_title="Large Synthetic Instrument",
            provider=provider,
        )
        approve_obligation(db_session, obligation=obligation, approved_by_user_id=owner.id)
        predicate = create_predicate(
            db_session,
            obligation=obligation,
            predicate_key=f"condition_{i}",
            # Alternate binds/does-not-bind/ambiguous so the run exercises
            # all three engine paths, not just one cheap branch.
            expression={"field": f"synthetic.field_{i % 3}", "equals": True},
        )
        approve_predicate(db_session, predicate=predicate, approved_by_user_id=owner.id)
    db_session.commit()

    profile = create_profile_version(
        db_session,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        created_by_user_id=owner.id,
        field_updates={
            "synthetic.field_0": FieldUpdate(True, ProfileFieldSource.USER),
            "synthetic.field_1": FieldUpdate(False, ProfileFieldSource.USER),
            # synthetic.field_2 deliberately left unanswered -> ambiguous.
        },
    )
    db_session.commit()

    started = time.perf_counter()
    analysis = run_analysis(
        db_session,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        entity_profile_id=profile.id,
        created_by_user_id=owner.id,
    )
    db_session.commit()
    elapsed = time.perf_counter() - started

    assert elapsed < 60, (
        f"Full-set evaluation took {elapsed:.2f}s for {_PREDICATE_COUNT} predicates"
    )

    views = list_analysis_item_views(db_session, analysis.id)
    assert len(views) == _PREDICATE_COUNT
    outcomes = {v.item.outcome.value for v in views}
    assert outcomes == {"binds", "does_not_bind", "ambiguous"}

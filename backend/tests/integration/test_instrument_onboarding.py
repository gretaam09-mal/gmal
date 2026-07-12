import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError

from db.models import Clause, CostTemplate, Instrument, InstrumentVersion, MetricsEvent
from db.models.enums import PredicateStatus
from services.extraction import ExtractedObligation, FixtureExtractionProvider
from services.instrument_onboarding import (
    ObligationLockedError,
    PredicateLockedError,
    approve_obligation,
    approve_predicate,
    attach_cost_template,
    correct_obligation,
    create_predicate,
    draft_predicate,
    extract_obligation,
    ingest_instrument,
    list_clauses,
    update_obligation,
    update_predicate,
)
from services.onboarding_metrics import ONBOARDING_COMPLETED_EVENT
from services.predicate_assist import DraftedPredicate, FixturePredicateAssistProvider

_RAW_TEXT = """1. A firm carrying out a regulated activity must appoint a compliance officer.

2. The compliance officer must report material breaches to the FCA within 14 days."""


def _extracted(summary="A firm must appoint a compliance officer.", clause_ref="s.1"):
    return ExtractedObligation.model_validate(
        {
            "summary": summary,
            "obligation_type": "appointment",
            "who": {
                "value": "firms carrying out a regulated activity",
                "clause_ref": clause_ref,
                "confidence": 92,
            },
            "what": {
                "value": "appoint a compliance officer",
                "clause_ref": clause_ref,
                "confidence": 95,
            },
            "when": {
                "value": "not specified in this clause",
                "clause_ref": clause_ref,
                "confidence": 30,
            },
            "threshold": {
                "value": "carries out a regulated activity",
                "clause_ref": clause_ref,
                "confidence": 88,
            },
            "enforcer": {"value": "the FCA", "clause_ref": clause_ref, "confidence": 70},
            "confidence": 85,
        }
    )


def test_ingest_instrument_creates_instrument_version_and_clauses(db_session):
    version = ingest_instrument(
        db_session,
        title="Test Compliance Act",
        jurisdiction="UK",
        kind="Act",
        citation="Test Act 2026",
        version_label="v1",
        source_url=None,
        raw_text=_RAW_TEXT,
    )
    db_session.commit()

    clauses = list_clauses(db_session, version.id)
    assert [c.clause_ref for c in clauses] == ["s.1", "s.2"]
    assert version.content_hash
    assert version.raw_text == _RAW_TEXT


def test_extract_obligation_persists_as_unapproved_draft(db_session):
    version = ingest_instrument(
        db_session,
        title="Test Act",
        jurisdiction="UK",
        kind="Act",
        citation=None,
        version_label="v1",
        source_url=None,
        raw_text=_RAW_TEXT,
    )
    clause = list_clauses(db_session, version.id)[0]
    provider = FixtureExtractionProvider({"s.1": _extracted()})

    obligation = extract_obligation(
        db_session, clause=clause, instrument_title="Test Act", provider=provider
    )
    db_session.commit()

    assert obligation.approved is False
    assert obligation.approved_by_user_id is None
    assert obligation.fields["who"]["clause_ref"] == "s.1"
    assert obligation.confidence == 85


def _ingest_and_extract(db_session):
    version = ingest_instrument(
        db_session,
        title="Test Act",
        jurisdiction="UK",
        kind="Act",
        citation=None,
        version_label="v1",
        source_url=None,
        raw_text=_RAW_TEXT,
    )
    clause = list_clauses(db_session, version.id)[0]
    provider = FixtureExtractionProvider({"s.1": _extracted()})
    obligation = extract_obligation(
        db_session, clause=clause, instrument_title="Test Act", provider=provider
    )
    db_session.commit()
    return obligation


def test_update_obligation_edits_while_draft(db_session):
    obligation = _ingest_and_extract(db_session)
    update_obligation(db_session, obligation=obligation, summary="Corrected summary.")
    db_session.commit()
    assert obligation.summary == "Corrected summary."


def test_approve_obligation_sets_approver_and_locks_it(db_session, make_user):
    obligation = _ingest_and_extract(db_session)
    approver = make_user()

    approve_obligation(db_session, obligation=obligation, approved_by_user_id=approver.id)
    db_session.commit()

    assert obligation.approved is True
    assert obligation.approved_by_user_id == approver.id
    assert obligation.approved_at is not None

    with pytest.raises(ObligationLockedError):
        update_obligation(db_session, obligation=obligation, summary="Trying to sneak an edit in.")


def test_db_trigger_rejects_raw_sql_update_of_approved_obligation(db_session, make_user):
    """Backstop test: even bypassing the service layer entirely and
    issuing a raw UPDATE, the DB itself refuses once approved=true."""
    obligation = _ingest_and_extract(db_session)
    approver = make_user()
    approve_obligation(db_session, obligation=obligation, approved_by_user_id=approver.id)
    db_session.commit()

    with pytest.raises(ProgrammingError, match="immutable"):
        db_session.execute(
            text("UPDATE obligations SET summary = 'hacked' WHERE id = :id"),
            {"id": str(obligation.id)},
        )
        db_session.flush()
    db_session.rollback()


def test_correct_obligation_versions_instead_of_mutating(db_session, make_user):
    obligation = _ingest_and_extract(db_session)
    approver = make_user()
    approve_obligation(db_session, obligation=obligation, approved_by_user_id=approver.id)
    db_session.commit()
    original_id = obligation.id

    corrected = correct_obligation(
        db_session,
        obligation=obligation,
        summary="A more precise summary.",
        obligation_type=obligation.obligation_type,
        fields=obligation.fields,
        confidence=obligation.confidence,
    )
    db_session.commit()

    assert corrected.id != original_id
    assert corrected.approved is False
    assert corrected.clause_id == obligation.clause_id
    assert obligation.valid_to is not None  # old row closed, not deleted


def test_approving_last_obligation_records_onboarding_hours_metric(db_session, make_user):
    obligation = _ingest_and_extract(db_session)
    approver = make_user()

    def _completion_events():
        return list(
            db_session.execute(
                select(MetricsEvent).where(MetricsEvent.event_name == ONBOARDING_COMPLETED_EVENT)
            ).scalars()
        )

    before = len(_completion_events())
    approve_obligation(db_session, obligation=obligation, approved_by_user_id=approver.id)
    db_session.commit()
    after_events = _completion_events()

    # This instrument has 2 clauses/potential obligations but only clause
    # s.1 was extracted — "fully approved" is defined over obligations
    # that exist, so approving the only one that exists completes it.
    assert len(after_events) == before + 1
    assert after_events[-1].properties["onboarding_hours"] >= 0


def test_onboarding_metric_is_recorded_only_once(db_session, make_user):
    obligation = _ingest_and_extract(db_session)
    approver = make_user()
    approve_obligation(db_session, obligation=obligation, approved_by_user_id=approver.id)
    db_session.commit()

    # A second, unrelated approval-triggering call (e.g. re-checking after
    # a correction cycle) must not double-record.
    from services.onboarding_metrics import maybe_record_onboarding_completion

    clause = db_session.get(Clause, obligation.clause_id)
    version = db_session.get(InstrumentVersion, clause.instrument_version_id)
    instrument = db_session.get(Instrument, version.instrument_id)

    maybe_record_onboarding_completion(db_session, instrument)
    db_session.commit()

    events = list(
        db_session.execute(
            select(MetricsEvent).where(MetricsEvent.event_name == ONBOARDING_COMPLETED_EVENT)
        ).scalars()
    )
    assert len(events) == 1


def test_draft_predicate_via_assist_starts_as_draft_never_approved(db_session):
    obligation = _ingest_and_extract(db_session)
    drafted = DraftedPredicate.model_validate(
        {
            "predicate_key": "regulated_activity",
            "expression": {"field": "footprint.regulated_activity", "equals": True},
            "explanation": "Applies to firms carrying out a regulated activity.",
        }
    )
    provider = FixturePredicateAssistProvider({obligation.summary: drafted})

    predicate = draft_predicate(
        db_session, obligation=obligation, available_fields=[], provider=provider
    )
    db_session.commit()

    assert predicate.status is PredicateStatus.DRAFT
    assert predicate.drafted_by_ai is True
    assert predicate.approved_by_user_id is None


def test_create_predicate_manually_also_starts_as_draft(db_session):
    obligation = _ingest_and_extract(db_session)
    predicate = create_predicate(
        db_session,
        obligation=obligation,
        predicate_key="manual_rule",
        expression={"field": "footprint.regulated_activity", "equals": True},
    )
    db_session.commit()
    assert predicate.status is PredicateStatus.DRAFT
    assert predicate.drafted_by_ai is False


def test_approve_predicate_locks_it(db_session, make_user):
    obligation = _ingest_and_extract(db_session)
    predicate = create_predicate(
        db_session,
        obligation=obligation,
        predicate_key="manual_rule",
        expression={"field": "footprint.regulated_activity", "equals": True},
    )
    approver = make_user()

    approve_predicate(db_session, predicate=predicate, approved_by_user_id=approver.id)
    db_session.commit()

    assert predicate.status is PredicateStatus.APPROVED
    with pytest.raises(PredicateLockedError):
        update_predicate(db_session, predicate=predicate, expression={"field": "x", "equals": 1})


def test_db_trigger_rejects_raw_sql_update_of_approved_predicate(db_session, make_user):
    obligation = _ingest_and_extract(db_session)
    predicate = create_predicate(
        db_session,
        obligation=obligation,
        predicate_key="manual_rule",
        expression={"field": "footprint.regulated_activity", "equals": True},
    )
    approver = make_user()
    approve_predicate(db_session, predicate=predicate, approved_by_user_id=approver.id)
    db_session.commit()

    with pytest.raises(ProgrammingError, match="immutable"):
        db_session.execute(
            text("UPDATE predicates SET predicate_key = 'hacked' WHERE id = :id"),
            {"id": str(predicate.id)},
        )
        db_session.flush()
    db_session.rollback()


def test_attach_cost_template_versions_instead_of_mutating(db_session):
    obligation = _ingest_and_extract(db_session)

    first = attach_cost_template(
        db_session,
        obligation=obligation,
        name="Compliance officer cost — rough",
        drivers=[{"key": "scale.employee_count", "label": "Employee count"}],
        formula={"base": 5000, "terms": [{"driver": "scale.employee_count", "rate": 40}]},
        currency="GBP",
        source_basis="expert estimate",
        maturity_tier="rough",
    )
    db_session.commit()
    assert first.valid_to is None

    second = attach_cost_template(
        db_session,
        obligation=obligation,
        name="Compliance officer cost — benchmarked",
        drivers=[{"key": "scale.employee_count", "label": "Employee count"}],
        formula={"base": 8000, "terms": [{"driver": "scale.employee_count", "rate": 55}]},
        currency="GBP",
        source_basis="vendor quote",
        maturity_tier="benchmarked",
    )
    db_session.commit()

    db_session.refresh(first)
    assert first.valid_to is not None  # closed, not deleted or edited
    assert second.valid_to is None
    assert second.id != first.id

    current = db_session.execute(
        select(CostTemplate).where(
            CostTemplate.obligation_id == obligation.id, CostTemplate.valid_to.is_(None)
        )
    ).scalar_one()
    assert current.id == second.id
    assert current.maturity_tier == "benchmarked"


def test_db_trigger_rejects_raw_sql_update_of_cost_template(db_session):
    obligation = _ingest_and_extract(db_session)
    template = attach_cost_template(
        db_session,
        obligation=obligation,
        name="x",
        drivers=[],
        formula={"base": 100},
        currency="GBP",
        source_basis="expert estimate",
        maturity_tier="rough",
    )
    db_session.commit()

    with pytest.raises(ProgrammingError, match="immutable"):
        db_session.execute(
            text("UPDATE cost_templates SET name = 'hacked' WHERE id = :id"),
            {"id": str(template.id)},
        )
        db_session.flush()
    db_session.rollback()

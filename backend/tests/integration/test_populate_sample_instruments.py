"""F3 spec: "Populate 3-4 SAMPLE/fixture instruments only, to prove the
pipeline end-to-end." Runs the actual seed script against the test
database rather than re-describing its logic — if the script breaks,
this breaks.
"""

from sqlalchemy import select

from db.models import Instrument, MetricsEvent, Obligation, Predicate
from db.models.enums import PredicateStatus
from scripts.populate_sample_instruments import _SAMPLE_INSTRUMENTS, populate
from services.onboarding_metrics import ONBOARDING_COMPLETED_EVENT


def test_populate_seeds_every_sample_instrument_fully_approved(db_session):
    assert len(_SAMPLE_INSTRUMENTS) >= 3

    populate()

    instruments = db_session.execute(select(Instrument)).scalars().all()
    assert {i.title for i in instruments} == {s["title"] for s in _SAMPLE_INSTRUMENTS}

    obligations = db_session.execute(select(Obligation)).scalars().all()
    assert len(obligations) == len(_SAMPLE_INSTRUMENTS)
    assert all(o.approved for o in obligations)

    predicates = db_session.execute(select(Predicate)).scalars().all()
    assert len(predicates) == len(_SAMPLE_INSTRUMENTS)
    assert all(p.status is PredicateStatus.APPROVED for p in predicates)

    metrics = db_session.execute(
        select(MetricsEvent).where(MetricsEvent.event_name == ONBOARDING_COMPLETED_EVENT)
    ).scalars().all()
    assert len(metrics) == len(_SAMPLE_INSTRUMENTS)


def test_populate_is_idempotent(db_session):
    populate()
    first_count = len(db_session.execute(select(Instrument)).scalars().all())

    populate()
    second_count = len(db_session.execute(select(Instrument)).scalars().all())

    assert first_count == second_count == len(_SAMPLE_INSTRUMENTS)

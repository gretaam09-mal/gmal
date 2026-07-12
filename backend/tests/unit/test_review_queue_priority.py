import uuid
from datetime import UTC, datetime, timedelta

from db.models.enums import MemoStatus
from services.review import ReviewQueueEntry, sort_review_queue

_NOW = datetime(2027, 1, 1, tzinfo=UTC)


def _entry(**overrides) -> ReviewQueueEntry:
    defaults = dict(
        memo_id=uuid.uuid4(),
        memo_title="Project Falcon",
        version_id=uuid.uuid4(),
        version_number=1,
        status=MemoStatus.IN_REVIEW,
        confidence_grade="B",
        ambiguous_count=0,
        submitted_at=_NOW,
        created_at=_NOW - timedelta(days=1),
    )
    defaults.update(overrides)
    return ReviewQueueEntry(**defaults)


def test_worse_confidence_grade_sorts_first():
    grade_a = _entry(confidence_grade="A")
    grade_d = _entry(confidence_grade="D")
    ordered = sort_review_queue([grade_a, grade_d])
    assert ordered == [grade_d, grade_a]


def test_missing_confidence_grade_is_treated_as_worst():
    grade_d = _entry(confidence_grade="D")
    no_grade = _entry(confidence_grade=None)
    ordered = sort_review_queue([grade_d, no_grade])
    assert ordered == [no_grade, grade_d]


def test_more_ambiguous_items_sorts_first_among_equal_grades():
    few = _entry(confidence_grade="B", ambiguous_count=1)
    many = _entry(confidence_grade="B", ambiguous_count=5)
    ordered = sort_review_queue([few, many])
    assert ordered == [many, few]


def test_older_submission_sorts_first_as_a_tiebreaker():
    newer = _entry(confidence_grade="B", ambiguous_count=0, submitted_at=_NOW)
    older = _entry(confidence_grade="B", ambiguous_count=0, submitted_at=_NOW - timedelta(days=3))
    ordered = sort_review_queue([newer, older])
    assert ordered == [older, newer]


def test_confidence_grade_beats_ambiguous_count():
    """A worse grade always outranks more ambiguous items on a better grade."""
    worse_grade_fewer_ambiguous = _entry(confidence_grade="C", ambiguous_count=0)
    better_grade_more_ambiguous = _entry(confidence_grade="A", ambiguous_count=10)
    ordered = sort_review_queue([better_grade_more_ambiguous, worse_grade_fewer_ambiguous])
    assert ordered == [worse_grade_fewer_ambiguous, better_grade_more_ambiguous]


def test_sort_is_deterministic():
    entries = [_entry(confidence_grade=g) for g in ("A", "C", "B", "D", "A")]
    assert sort_review_queue(entries) == sort_review_queue(list(entries))

from engine.completeness.calculator import FieldState, compute_completeness
from engine.completeness.catalog import FIELD_CATALOG


def test_all_fields_confirmed_scores_full_marks():
    field_states = {field.key: FieldState(field.key, "user") for field in FIELD_CATALOG}

    result = compute_completeness(field_states)

    assert result.overall_score == 1.0
    assert result.unknown_field_labels == ()
    for section in result.sections:
        assert section.score == 1.0


def test_no_fields_known_scores_zero_and_lists_every_label():
    result = compute_completeness({})

    assert result.overall_score == 0.0
    assert len(result.unknown_field_labels) == len(FIELD_CATALOG)


def test_unknown_source_counts_as_unknown_even_if_present():
    field_states = {field.key: FieldState(field.key, "unknown") for field in FIELD_CATALOG}

    result = compute_completeness(field_states)

    assert result.overall_score == 0.0
    assert len(result.unknown_field_labels) == len(FIELD_CATALOG)


def test_default_and_estimate_get_half_credit():
    field_states = {field.key: FieldState(field.key, "default") for field in FIELD_CATALOG}

    result = compute_completeness(field_states)

    assert result.overall_score == 0.5
    assert result.unknown_field_labels == ()  # "default" isn't unknown, just unconfirmed


def test_one_unknown_footprint_field_flags_that_section():
    field_states = {field.key: FieldState(field.key, "registry") for field in FIELD_CATALOG}
    del field_states["footprint.holds_client_money"]  # simulate never having been answered

    result = compute_completeness(field_states)

    assert result.overall_score < 1.0
    assert "Holds client money or assets?" in result.unknown_field_labels
    footprint_section = next(s for s in result.sections if s.section == "footprint")
    assert footprint_section.score < 1.0
    other_sections = [s for s in result.sections if s.section != "footprint"]
    assert all(s.score == 1.0 for s in other_sections)


def test_is_deterministic():
    field_states = {
        "identity.company_name": FieldState("identity.company_name", "registry"),
        "footprint.employs_staff": FieldState("footprint.employs_staff", "unknown"),
    }

    first = compute_completeness(field_states)
    second = compute_completeness(field_states)

    assert first == second

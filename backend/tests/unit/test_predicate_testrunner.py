from engine.predicates import PredicateOutcome
from services.predicate_testrunner import load_fixture_profiles, run_predicate_against_fixtures


def test_load_fixture_profiles_finds_all_four_archetypes():
    profiles = load_fixture_profiles()
    assert set(profiles) == {
        "small_uk_advisory_firm",
        "regulated_asset_manager",
        "dormant_holding_co",
        "manufacturing_exporter",
    }


def test_run_predicate_against_fixtures_covers_all_three_outcomes():
    """holds_client_money is True/False/unset across the four fixtures —
    exactly the point of having four archetypes, not one."""
    expression = {"field": "footprint.holds_client_money", "equals": True}
    results = {r.profile_name: r for r in run_predicate_against_fixtures(expression)}

    assert results["regulated_asset_manager"].outcome is PredicateOutcome.BINDS
    assert results["small_uk_advisory_firm"].outcome is PredicateOutcome.DOES_NOT_BIND
    assert results["dormant_holding_co"].outcome is PredicateOutcome.DOES_NOT_BIND
    assert results["manufacturing_exporter"].outcome is PredicateOutcome.AMBIGUOUS
    assert results["manufacturing_exporter"].missing_field_keys == (
        "footprint.holds_client_money",
    )


def test_run_predicate_against_fixtures_is_sorted_by_profile_name():
    expression = {"field": "footprint.employs_staff", "equals": True}
    results = run_predicate_against_fixtures(expression)
    assert [r.profile_name for r in results] == sorted(r.profile_name for r in results)

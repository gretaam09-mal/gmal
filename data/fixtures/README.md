# Fixtures

Sample/synthetic data for local development and tests — no real client or
deal data.

- `companies_house/` — canned Companies House API responses (F2).
- `company_profiles/` — four synthetic entity-profile fact sets (flat
  `field_key -> value`, matching `backend/engine/completeness/catalog.py`),
  used by the F3 predicate test-runner
  (`backend/services/predicate_testrunner.py`) and the golden set. Each
  is deliberately a different archetype and deliberately incomplete in
  places (some footprint/cost-sketch fields are omitted) so a predicate
  test run exercises binds, does-not-bind, *and* ambiguous outcomes, not
  just the happy path:
  - `small_uk_advisory_firm` — unregulated, no client money, no overseas ops.
  - `regulated_asset_manager` — FCA-regulated, holds client money, overseas ops.
  - `dormant_holding_co` — no activity, cost-sketch fields unknown.
  - `manufacturing_exporter` — handles hazardous materials, `holds_client_money` unknown.

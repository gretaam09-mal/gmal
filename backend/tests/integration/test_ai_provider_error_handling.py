"""A missing or invalid PROVISION_ANTHROPIC_API_KEY must never surface as
an unhandled 500 — every AI-touching admin route has to fail with a
clear, human-readable message. services/ai/anthropic_calls.py (see
tests/unit/test_anthropic_calls.py) pins that an SDK-level failure
becomes a clear domain error; these tests pin the other half — that the
*dependency construction* failure (no key at all) and a domain error
raised from inside a route both come back as a clean HTTP response
instead of a raw 500, via api/main.py's global exception handlers.
"""
from api.deps import get_extraction_provider
from api.main import app
from services.extraction.anthropic_provider import ExtractionNotConfiguredError
from services.extraction.provider import ExtractionError

_RAW_TEXT = (
    "1. A firm that processes personal data at scale must appoint a data protection officer."
)


def _make_staff(make_user, db_session):
    staff = make_user()
    staff.is_staff = True
    db_session.commit()
    return staff


def _seeded_clause_id(client):
    resp = client.post(
        "/admin/instruments",
        json={
            "title": "Test Data Protection Act",
            "jurisdiction": "UK",
            "kind": "Act",
            "version_label": "v1",
            "raw_text": _RAW_TEXT,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["versions"][0]["clauses"][0]["id"]


def test_extraction_not_configured_error_is_a_subclass_of_extraction_error():
    """The dependency-injection-time failure mode (missing key) and the
    route-body failure mode (bad key, API outage) must share a type so
    one exception handler covers both — see api/main.py."""
    assert issubclass(ExtractionNotConfiguredError, ExtractionError)


def test_missing_anthropic_key_produces_a_clean_502_not_a_500(client_as, make_user, db_session):
    """No test in this repo (nor the deployed app, until someone sets
    PROVISION_ANTHROPIC_API_KEY) configures a real key, so this exercises
    the actual default dependency: AnthropicExtractionProvider() raising
    ExtractionNotConfiguredError during FastAPI's dependency resolution,
    before the route body's own try/except ever runs."""
    staff = _make_staff(make_user, db_session)
    client = client_as(staff)
    clause_id = _seeded_clause_id(client)

    resp = client.post(
        f"/admin/clauses/{clause_id}/obligations/extract",
        json={"instrument_title": "Test Data Protection Act"},
    )

    assert resp.status_code == 502, resp.text
    detail = resp.json()["detail"]
    assert "PROVISION_ANTHROPIC_API_KEY" in detail


def test_provider_error_raised_from_the_route_body_is_also_a_clean_502(
    client_as, make_user, db_session
):
    """Once a key IS configured, a rejected key or an API outage surfaces
    as ExtractionError from inside extract_obligation (via create_message
    — see test_anthropic_calls.py) rather than at construction time; this
    proves the route's own try/except handles that path too."""

    class _RejectingProvider:
        def extract(self, **kwargs):
            raise ExtractionError(
                "The Anthropic API rejected the configured key — check that "
                "PROVISION_ANTHROPIC_API_KEY is set to a valid key."
            )

    app.dependency_overrides[get_extraction_provider] = lambda: _RejectingProvider()
    try:
        staff = _make_staff(make_user, db_session)
        client = client_as(staff)
        clause_id = _seeded_clause_id(client)

        resp = client.post(
            f"/admin/clauses/{clause_id}/obligations/extract",
            json={"instrument_title": "Test Data Protection Act"},
        )

        assert resp.status_code == 502, resp.text
        assert "rejected the configured key" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_extraction_provider, None)

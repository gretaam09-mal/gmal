import json
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi import Header, HTTPException, status
from fastapi.testclient import TestClient

from api.deps import get_companies_house_client, get_current_user
from api.main import app
from db.models import User
from db.session import raw_session
from services.companies_house import CompaniesHouseClient

FIXTURES = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "companies_house"


@pytest.fixture
def make_user(db_session):
    def _make(email: str | None = None) -> User:
        suffix = uuid.uuid4().hex[:8]
        user = User(clerk_user_id=f"clerk_{suffix}", email=email or f"user-{suffix}@example.com")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make


def _test_current_user(x_test_user_id: str = Header(...)) -> User:
    """Test-only replacement for get_current_user.

    Reads identity from a header instead of a real Clerk bearer token, so
    each TestClient can carry its own default header and multiple
    "logged in as" clients can coexist — unlike closing over a fixed user
    in the override callable, which app.dependency_overrides (a single
    dict on the shared `app`) would silently clobber between clients.
    """
    with raw_session() as session:
        user = session.get(User, uuid.UUID(x_test_user_id))
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown test user")
        return user


@pytest.fixture
def client_as():
    """A TestClient authenticated as `user`, bypassing real Clerk verification.

    get_current_user is the only thing overridden — every route still runs
    its real tenancy/RBAC/audit/RLS logic against the real test database.
    """
    app.dependency_overrides[get_current_user] = _test_current_user

    def _client(user: User) -> TestClient:
        client = TestClient(app)
        client.headers.update({"X-Test-User-Id": str(user.id)})
        return client

    yield _client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def companies_house_fixture():
    """Overrides get_companies_house_client with one backed by local
    fixtures — no route test in this repo ever calls the real API."""
    profiles = {
        "12345678": json.loads((FIXTURES / "company_profile_active.json").read_text()),
        "87654321": json.loads((FIXTURES / "company_profile_dormant_micro.json").read_text()),
    }
    officers = {
        "12345678": json.loads((FIXTURES / "officers_active.json").read_text()),
        "87654321": json.loads((FIXTURES / "officers_empty.json").read_text()),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        parts = request.url.path.strip("/").split("/")
        company_number = parts[1]
        if len(parts) == 2:
            data = profiles.get(company_number)
        elif len(parts) == 3 and parts[2] == "officers":
            data = officers.get(company_number)
        else:
            data = None
        if data is None:
            return httpx.Response(404, json={"errors": [{"error": "not-found"}]})
        return httpx.Response(200, json=data)

    def _override():
        with CompaniesHouseClient(api_key="test", transport=httpx.MockTransport(handler)) as c:
            yield c

    app.dependency_overrides[get_companies_house_client] = _override
    yield
    app.dependency_overrides.pop(get_companies_house_client, None)


@pytest.fixture
def composition_provider_fixture():
    """Overrides get_composition_provider with an explicitly-registered
    FixtureCompositionProvider — no route test in this repo ever calls
    the real P-COMPOSE model. Tests register the prose they expect
    before hitting the HTTP endpoint."""
    from api.deps import get_composition_provider
    from services.composition.fixture_provider import FixtureCompositionProvider

    provider = FixtureCompositionProvider()
    app.dependency_overrides[get_composition_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_composition_provider, None)


@pytest.fixture
def diff_note_provider_fixture():
    """Overrides get_diff_note_provider with a deterministic stand-in that
    mechanically renders a note from the Change tuple it's given (always
    traceable, since it's built from the same before/after values) — good
    enough for HTTP round-trip tests that only care that the endpoint
    wires the diff through, not about prose quality."""
    from api.deps import get_diff_note_provider
    from services.diff_note.schemas import ComposedDiffNote
    from services.diff_note.validator import validate_diff_note

    class _AutoDiffNoteProvider:
        def summarise(self, changes):
            parts = [f"{c.field} changed from {c.before} to {c.after}." for c in changes]
            note = ComposedDiffNote.model_validate(
                {"change_note": " ".join(parts) or "No changes."}
            )
            validate_diff_note(note, changes)
            return note

    provider = _AutoDiffNoteProvider()
    app.dependency_overrides[get_diff_note_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_diff_note_provider, None)

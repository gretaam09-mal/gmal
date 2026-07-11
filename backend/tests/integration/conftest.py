import uuid

import pytest
from fastapi import Header, HTTPException, status
from fastapi.testclient import TestClient

from api.deps import get_current_user
from api.main import app
from db.models import User
from db.session import raw_session


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

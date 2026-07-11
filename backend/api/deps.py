import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING

from fastapi import Depends, Header, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Membership, MembershipStatus, Role, User
from db.session import raw_session, set_user_context, workspace_session
from services.auth.clerk import ClerkAuthError, verify_clerk_token
from services.companies_house import CompaniesHouseClient

if TYPE_CHECKING:
    from services.extraction.provider import ExtractionProvider
    from services.predicate_assist.provider import PredicateAssistProvider


def get_raw_session() -> Iterator[Session]:
    """A session bound to one connection for the request. Only used for
    identity lookups and handlers that need to mix an unscoped read (e.g.
    "does this tenant exist") with RLS-scoped writes via set_rls_context
    on the same connection — see api/routes/tenants.py. Everything else
    should use get_workspace_db.
    """
    with raw_session() as session:
        yield session


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_raw_session),
) -> User:
    """Verify the Clerk bearer token and return (creating on first sight) the
    corresponding User row. Every workspace-scoped route depends on this
    transitively via get_workspace_membership.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        claims = verify_clerk_token(token)
    except ClerkAuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user = session.execute(
        select(User).where(User.clerk_user_id == claims.clerk_user_id)
    ).scalar_one_or_none()
    if user is None:
        user = User(
            clerk_user_id=claims.clerk_user_id,
            email=claims.email or f"{claims.clerk_user_id}@users.provision.invalid",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def get_workspace_membership(
    workspace_id: uuid.UUID = Path(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_raw_session),
) -> Membership:
    """CONVENTIONS.md rule #3 + tenancy: every workspace-scoped route
    depends on this (directly or via require_role). It is the single
    place that turns "a user and a workspace id in the URL" into "is this
    user actually an active member of that workspace" — a 404 (not 403)
    on failure so a workspace's existence isn't leaked to non-members.

    This runs before the caller's tenant_id is known, so it can't use
    workspace_session yet — set_user_context opens a narrow bootstrap
    path (memberships_self_read policy) that only ever exposes a user's
    own membership rows, never anyone else's.
    """
    set_user_context(session, current_user.id)
    membership = session.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == current_user.id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return membership


def get_workspace_db(
    membership: Membership = Depends(get_workspace_membership),
) -> Iterator[Session]:
    """A Session scoped (via Postgres RLS) to exactly this membership's
    tenant and workspace. Use this for every query in a workspace-scoped
    route instead of get_raw_session.
    """
    with workspace_session(membership.tenant_id, membership.workspace_id) as session:
        yield session


def get_companies_house_client() -> Iterator[CompaniesHouseClient]:
    """A dependency (not a plain import) so tests can override it with a
    fixture-backed client instead of one that hits the real API — see
    tests/integration/conftest.py::companies_house_client_as.
    """
    with CompaniesHouseClient() as client:
        yield client


def get_extraction_provider() -> "ExtractionProvider":
    """Real P-EXTRACT provider by default; tests override this with
    FixtureExtractionProvider (see tests/integration/conftest.py) so no
    test in this repo makes a live model call. Constructing
    AnthropicExtractionProvider here (not at import time) is what makes
    it fail closed with a clear error when no key is configured, instead
    of at app startup.
    """
    from services.extraction.anthropic_provider import AnthropicExtractionProvider

    return AnthropicExtractionProvider()


def get_predicate_assist_provider() -> "PredicateAssistProvider":
    """See get_extraction_provider — same fail-closed-without-a-key shape,
    for P-PREDICATE-ASSIST (services/predicate_assist.py)."""
    from services.predicate_assist import AnthropicPredicateAssistProvider

    return AnthropicPredicateAssistProvider()


def require_staff(current_user: User = Depends(get_current_user)) -> User:
    """Gates the F3 instrument-onboarding workbench (/admin/* routes).

    Unrelated to workspace Role — instruments/obligations/predicates are
    shared reference data, not tenant data (see db/models/regulatory.py),
    so this is a separate, coarser gate: staff or not. Nobody is staff by
    default (User.is_staff defaults False); grant it with
    backend/scripts/grant_staff.py. Fails closed, and this tooling is
    never linked from the client-facing UI regardless.
    """
    if not current_user.is_staff:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff access required")
    return current_user


def require_role(*roles: Role):
    """Dependency factory: 403s unless the caller's role in this workspace
    is one of `roles`. Composes with get_workspace_membership, so routes
    that need a specific role don't also need to depend on it separately.
    """

    def _check(membership: Membership = Depends(get_workspace_membership)) -> Membership:
        if membership.role not in roles:
            allowed = ", ".join(role.value for role in roles)
            detail = f"Requires role: {allowed} (you are {membership.role.value})"
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail)
        return membership

    return _check

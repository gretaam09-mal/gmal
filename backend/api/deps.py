import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING

from fastapi import Depends, Header, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import get_settings
from db.models import Membership, MembershipStatus, Role, User
from db.session import raw_session, set_user_context, workspace_session
from services.audit import record_audit_event
from services.auth.clerk import ClerkAuthError, verify_clerk_token
from services.companies_house import CompaniesHouseClient

if TYPE_CHECKING:
    from services.composition.provider import CompositionProvider
    from services.cost_estimate.provider import CostEstimateProvider
    from services.diff_note.provider import DiffNoteProvider
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


def _maybe_elevate_to_staff(session: Session, user: User) -> None:
    """PROVISION_ADMIN_EMAILS: a comma-separated allowlist an operator sets
    so they can reach /admin without a manual scripts/grant_staff.py run
    against the deployed database. Elevation-only and idempotent by
    construction:

    - No-op the moment is_staff is already True — this function can never
      touch is_staff (or anything else) once staff access is granted, so
      it cannot be used to demote someone dropped from the list, and
      running it every request never writes more than once per user.
    - Only ever sets is_staff True; there is no code path here that sets
      it False. Revocation stays a deliberate, separate action
      (scripts/grant_staff.py --revoke).
    - Staff only unlocks /admin's shared reference-data routes (see
      require_staff) — it carries no workspace Role and does not touch
      tenant scoping or row-level security anywhere.
    """
    if user.is_staff:
        return
    if user.email.lower() not in get_settings().admin_emails_list:
        return
    user.is_staff = True
    record_audit_event(
        session,
        tenant_id=None,
        actor_user_id=user.id,
        action="auth.staff_granted_via_admin_emails",
        entity_type="user",
        entity_id=user.id,
    )
    session.commit()
    session.refresh(user)


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
        session.flush()
        record_audit_event(
            session,
            tenant_id=None,
            actor_user_id=user.id,
            action="auth.first_sign_in",
            entity_type="user",
            entity_id=user.id,
        )
        session.commit()
        session.refresh(user)
    elif claims.email and user.email != claims.email:
        # Clerk is the source of truth for identity, and its session token
        # doesn't always carry an email claim (depends on the Clerk
        # Dashboard's session token customization — see
        # docs/runbooks/clerk-setup.md); a user created before that was
        # configured has the synthetic "{clerk_user_id}@users.provision.
        # invalid" placeholder from the branch above forever otherwise.
        # Re-syncing here means PROVISION_ADMIN_EMAILS elevation (below)
        # and invite-acceptance-by-email (api/routes/invites.py) start
        # working on this user's very next request once Clerk starts
        # sending a real email — no sign-out needed.
        user.email = claims.email
        session.commit()
        session.refresh(user)
    _maybe_elevate_to_staff(session, user)
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
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found")
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


def get_composition_provider() -> "CompositionProvider":
    """See get_extraction_provider — same fail-closed-without-a-key shape,
    for P-COMPOSE (services/composition.py)."""
    from services.composition import AnthropicCompositionProvider

    return AnthropicCompositionProvider()


def get_diff_note_provider() -> "DiffNoteProvider":
    """See get_extraction_provider — same fail-closed-without-a-key shape,
    for P-DIFF-NOTE (services/diff_note.py)."""
    from services.diff_note import AnthropicDiffNoteProvider

    return AnthropicDiffNoteProvider()


def get_cost_estimate_provider() -> "CostEstimateProvider":
    """See get_extraction_provider — same fail-closed-without-a-key shape,
    for P-COST-ESTIMATE (services/cost_estimate.py). CONVENTIONS.md rule
    1's narrow cost-estimation exception: the one AI call allowed to
    originate a number a user sees, so it fails closed exactly like every
    other AI provider here rather than silently falling back to
    inventing a figure or dropping the obligation's cost."""
    from services.cost_estimate import AnthropicCostEstimateProvider

    return AnthropicCostEstimateProvider()


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

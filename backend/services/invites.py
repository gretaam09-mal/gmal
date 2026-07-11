import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from api.config import get_settings

_ALGORITHM = "HS256"
_TOKEN_TTL = timedelta(days=14)


class InviteTokenError(Exception):
    """Raised when an invite token is malformed, expired, or forged."""


@dataclass(frozen=True)
class InviteTokenClaims:
    tenant_id: uuid.UUID
    workspace_id: uuid.UUID
    membership_id: uuid.UUID


def create_invite_token(
    *, tenant_id: uuid.UUID, workspace_id: uuid.UUID, membership_id: uuid.UUID
) -> str:
    """Sign a capability token for one pending membership invite.

    Deliberately self-contained (not a DB lookup key): accepting an invite
    is inherently a cross-tenant operation (the invitee isn't a member of
    anything yet), and CONVENTIONS.md rule #3's row-level security would
    block any query that isn't already scoped to a tenant/workspace. A
    signed token that carries its own tenant/workspace lets acceptance
    open a normally-scoped session instead of needing an RLS bypass.
    """
    now = datetime.now(UTC)
    payload = {
        "tenant_id": str(tenant_id),
        "workspace_id": str(workspace_id),
        "membership_id": str(membership_id),
        "iat": now,
        "exp": now + _TOKEN_TTL,
    }
    return jwt.encode(payload, get_settings().app_secret_key, algorithm=_ALGORITHM)


def verify_invite_token(token: str) -> InviteTokenClaims:
    try:
        payload = jwt.decode(token, get_settings().app_secret_key, algorithms=[_ALGORITHM])
        return InviteTokenClaims(
            tenant_id=uuid.UUID(payload["tenant_id"]),
            workspace_id=uuid.UUID(payload["workspace_id"]),
            membership_id=uuid.UUID(payload["membership_id"]),
        )
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InviteTokenError(f"invalid invite token: {exc}") from exc

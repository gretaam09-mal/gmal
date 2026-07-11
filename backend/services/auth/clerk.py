from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from api.config import get_settings


class ClerkAuthError(Exception):
    """Raised when a bearer token fails Clerk verification."""


class ClerkNotConfiguredError(ClerkAuthError):
    """Raised when no Clerk JWKS URL is configured yet.

    See docs/adr/0001-clerk-for-authentication.md and
    docs/runbooks/clerk-setup.md — until PROVISION_CLERK_JWKS_URL is set,
    every authenticated request correctly fails closed rather than
    silently accepting unverified tokens.
    """


@dataclass(frozen=True)
class ClerkClaims:
    clerk_user_id: str
    email: str | None


_jwk_client: PyJWKClient | None = None


def _get_jwk_client() -> PyJWKClient:
    global _jwk_client
    settings = get_settings()
    if not settings.clerk_jwks_url:
        raise ClerkNotConfiguredError("PROVISION_CLERK_JWKS_URL is not set")
    if _jwk_client is None or _jwk_client.uri != settings.clerk_jwks_url:
        _jwk_client = PyJWKClient(settings.clerk_jwks_url)
    return _jwk_client


def verify_clerk_token(token: str, *, jwk_client: PyJWKClient | None = None) -> ClerkClaims:
    """Verify a Clerk session JWT and return its identity claims.

    `jwk_client` is injectable so tests can verify against a locally
    generated keypair instead of Clerk's real JWKS endpoint.
    """
    settings = get_settings()
    client = jwk_client or _get_jwk_client()
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"verify_iss": settings.clerk_issuer is not None, "verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise ClerkAuthError(f"invalid token: {exc}") from exc

    clerk_user_id = payload.get("sub")
    if not clerk_user_id:
        raise ClerkAuthError("token missing sub claim")
    return ClerkClaims(clerk_user_id=clerk_user_id, email=payload.get("email"))

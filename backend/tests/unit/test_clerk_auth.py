import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK

from services.auth.clerk import ClerkAuthError, verify_clerk_token


class _StaticJWKClient:
    """A jwt.PyJWKClient stand-in returning a fixed local keypair, so tests
    never hit Clerk's real JWKS endpoint over the network."""

    def __init__(self, public_key):
        self._jwk = PyJWK.from_json(
            json.dumps(
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "n": jwt.utils.to_base64url_uint(public_key.public_numbers().n).decode(),
                    "e": jwt.utils.to_base64url_uint(public_key.public_numbers().e).decode(),
                }
            )
        )

    def get_signing_key_from_jwt(self, _token: str):
        return self._jwk


@pytest.fixture
def keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _sign(private_key, claims: dict) -> str:
    return jwt.encode(claims, private_key, algorithm="RS256")


def test_verify_clerk_token_returns_claims(keypair):
    private_key, public_key = keypair
    now = datetime.now(UTC)
    claims_in = {
        "sub": "user_abc123",
        "email": "a@example.com",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    token = _sign(private_key, claims_in)

    claims = verify_clerk_token(token, jwk_client=_StaticJWKClient(public_key))

    assert claims.clerk_user_id == "user_abc123"
    assert claims.email == "a@example.com"


def test_verify_clerk_token_rejects_expired_token(keypair):
    private_key, public_key = keypair
    past = datetime.now(UTC) - timedelta(hours=2)
    claims_in = {"sub": "user_abc123", "iat": past, "exp": past + timedelta(minutes=1)}
    token = _sign(private_key, claims_in)

    with pytest.raises(ClerkAuthError):
        verify_clerk_token(token, jwk_client=_StaticJWKClient(public_key))


def test_verify_clerk_token_rejects_wrong_signing_key(keypair):
    _private_key, public_key = keypair
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    claims_in = {"sub": "user_abc123", "iat": now, "exp": now + timedelta(hours=1)}
    token = _sign(other_private_key, claims_in)

    with pytest.raises(ClerkAuthError):
        verify_clerk_token(token, jwk_client=_StaticJWKClient(public_key))


def test_verify_clerk_token_rejects_missing_sub(keypair):
    private_key, public_key = keypair
    now = datetime.now(UTC)
    token = _sign(private_key, {"iat": now, "exp": now + timedelta(hours=1)})

    with pytest.raises(ClerkAuthError):
        verify_clerk_token(token, jwk_client=_StaticJWKClient(public_key))

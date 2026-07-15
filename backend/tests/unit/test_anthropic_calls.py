"""services/ai/anthropic_calls.py is the one place every Anthropic-backed
provider (extraction, composition, predicate_assist, diff_note) routes
its SDK call through — these tests pin that a missing/invalid key or a
connection failure always comes out as the caller's own domain error
with a clear, human-readable message, never a raw SDK exception."""

import httpx
import pytest
from anthropic import APIConnectionError, APIStatusError, AuthenticationError

from services.ai.anthropic_calls import create_message


class _DomainError(Exception):
    pass


class _RaisingMessages:
    def __init__(self, exc: Exception):
        self._exc = exc

    def create(self, **kwargs):
        raise self._exc


class _FakeClient:
    def __init__(self, exc: Exception):
        self.messages = _RaisingMessages(exc)


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def test_authentication_error_becomes_a_clear_domain_error():
    response = httpx.Response(401, request=_request())
    exc = AuthenticationError("invalid x-api-key", response=response, body=None)
    client = _FakeClient(exc)

    with pytest.raises(_DomainError) as excinfo:
        create_message(client, _DomainError, model="m")

    assert "PROVISION_ANTHROPIC_API_KEY" in str(excinfo.value)
    assert excinfo.value.__cause__ is exc


def test_connection_error_becomes_a_clear_domain_error():
    exc = APIConnectionError(message="Connection error.", request=_request())
    client = _FakeClient(exc)

    with pytest.raises(_DomainError) as excinfo:
        create_message(client, _DomainError, model="m")

    assert "Could not reach the Anthropic API" in str(excinfo.value)


def test_generic_status_error_becomes_a_clear_domain_error():
    response = httpx.Response(500, request=_request())
    exc = APIStatusError("internal error", response=response, body=None)
    client = _FakeClient(exc)

    with pytest.raises(_DomainError) as excinfo:
        create_message(client, _DomainError, model="m")

    assert "status 500" in str(excinfo.value)


def test_successful_call_passes_through_unchanged():
    class _OkMessages:
        def create(self, **kwargs):
            return {"ok": True, "kwargs": kwargs}

    class _OkClient:
        def __init__(self):
            self.messages = _OkMessages()

    result = create_message(_OkClient(), _DomainError, model="m", max_tokens=1)
    assert result == {"ok": True, "kwargs": {"model": "m", "max_tokens": 1}}

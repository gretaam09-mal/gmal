"""KimiProvider (services/ai/kimi_provider.py) — Moonshot's OpenAI-
compatible chat completions API. Every test here runs against a mocked
httpx.Client (httpx.MockTransport); nothing ever reaches the real
Moonshot API — the gate test the spec requires ("a public call to kimi
succeeds against a mocked client") lives here.
"""
from __future__ import annotations

import json

import httpx
import pytest

from services.ai.kimi_provider import KimiProvider


class _DomainError(Exception):
    pass


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://api.moonshot.ai/v1",
        transport=httpx.MockTransport(handler),
    )


def _chat_response(content: dict | str) -> httpx.Response:
    body = json.dumps(content) if isinstance(content, dict) else content
    return httpx.Response(200, json={"choices": [{"message": {"content": body}}]})


def test_public_call_to_kimi_succeeds_against_a_mocked_client():
    """The gate test the spec requires: a public call to kimi succeeds
    against a mocked client. Also pins the request shape sent — model,
    system+messages folded into one list, and response_format carrying
    the declared JSON schema."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return _chat_response({"summary": "Firms must appoint a DPO.", "confidence": 90})

    provider = KimiProvider(api_key="test-moonshot-key", client=_client(handler))

    result = provider.generate_structured(
        _DomainError,
        model=None,
        max_tokens=512,
        system="You extract obligations.",
        messages=[{"role": "user", "content": "Clause 1: appoint a DPO."}],
        tool_name="record_extracted_obligation",
        tool_description="Records the extracted obligation.",
        input_schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}, "confidence": {"type": "integer"}},
            "required": ["summary", "confidence"],
        },
    )

    assert result == {"summary": "Firms must appoint a DPO.", "confidence": 90}
    assert captured["url"] == "https://api.moonshot.ai/v1/chat/completions"
    assert captured["auth"] == "Bearer test-moonshot-key"
    assert captured["body"]["model"] == "kimi-k3"
    assert captured["body"]["messages"][0] == {
        "role": "system",
        "content": "You extract obligations.",
    }
    assert captured["body"]["messages"][1] == {
        "role": "user",
        "content": "Clause 1: appoint a DPO.",
    }
    assert captured["body"]["response_format"]["type"] == "json_schema"
    assert captured["body"]["response_format"]["json_schema"]["name"] == (
        "record_extracted_obligation"
    )
    assert captured["body"]["response_format"]["json_schema"]["schema"]["required"] == [
        "summary",
        "confidence",
    ]


def test_a_custom_model_override_is_sent_verbatim():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "kimi-k2.5"
        return _chat_response({"ok": True})

    provider = KimiProvider(api_key="key", client=_client(handler))
    result = provider.generate_structured(
        _DomainError,
        model="kimi-k2.5",
        max_tokens=100,
        system="s",
        messages=[{"role": "user", "content": "hi"}],
        tool_name="t",
        tool_description="d",
        input_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )
    assert result == {"ok": True}


def test_retries_once_on_non_json_content_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _chat_response("not valid json at all")
        return _chat_response({"ok": True})

    provider = KimiProvider(api_key="key", client=_client(handler))
    result = provider.generate_structured(
        _DomainError,
        model=None,
        max_tokens=100,
        system="s",
        messages=[{"role": "user", "content": "hi"}],
        tool_name="t",
        tool_description="d",
        input_schema={"type": "object"},
    )
    assert result == {"ok": True}
    assert calls["n"] == 2


def test_raises_the_domain_error_after_both_attempts_fail_to_parse():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response("still not json")

    provider = KimiProvider(api_key="key", client=_client(handler))
    with pytest.raises(_DomainError, match="did not produce valid structured output"):
        provider.generate_structured(
            _DomainError,
            model=None,
            max_tokens=100,
            system="s",
            messages=[{"role": "user", "content": "hi"}],
            tool_name="t",
            tool_description="d",
            input_schema={"type": "object"},
        )


def test_missing_api_key_raises_the_domain_error_before_any_request():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should have been made without a key")

    provider = KimiProvider(api_key=None, client=_client(handler))
    with pytest.raises(_DomainError, match="MOONSHOT_API_KEY"):
        provider.generate_structured(
            _DomainError,
            model=None,
            max_tokens=100,
            system="s",
            messages=[{"role": "user", "content": "hi"}],
            tool_name="t",
            tool_description="d",
            input_schema={"type": "object"},
        )


def test_a_401_response_becomes_a_clear_domain_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    provider = KimiProvider(api_key="bad-key", client=_client(handler))
    with pytest.raises(_DomainError, match="rejected the configured key"):
        provider.generate_structured(
            _DomainError,
            model=None,
            max_tokens=100,
            system="s",
            messages=[{"role": "user", "content": "hi"}],
            tool_name="t",
            tool_description="d",
            input_schema={"type": "object"},
        )


def test_a_connection_failure_becomes_a_clear_domain_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = KimiProvider(api_key="key", client=_client(handler))
    with pytest.raises(_DomainError, match="Could not reach the Moonshot API"):
        provider.generate_structured(
            _DomainError,
            model=None,
            max_tokens=100,
            system="s",
            messages=[{"role": "user", "content": "hi"}],
            tool_name="t",
            tool_description="d",
            input_schema={"type": "object"},
        )


def test_generate_text_returns_the_plain_content():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response("Plain text reply.")

    provider = KimiProvider(api_key="key", client=_client(handler))
    result = provider.generate_text(
        _DomainError,
        model=None,
        max_tokens=100,
        system="s",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert result == "Plain text reply."

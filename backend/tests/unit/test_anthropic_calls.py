"""services/ai/anthropic_calls.py is the one place every Anthropic-backed
provider (extraction, composition, predicate_assist, diff_note) routes
its SDK call through — these tests pin that a missing/invalid key or a
connection failure always comes out as the caller's own domain error
with a clear, human-readable message, never a raw SDK exception."""

import httpx
import pytest
from anthropic import APIConnectionError, APIStatusError, AuthenticationError

from services.ai.anthropic_calls import create_json_message, create_message, extract_json_object


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


# --- extract_json_object -----------------------------------------------------


def test_extract_json_object_returns_plain_json_unchanged():
    assert extract_json_object('{"a": 1}') == '{"a": 1}'


def test_extract_json_object_strips_a_json_fence():
    raw = '```json\n{"a": 1}\n```'
    assert extract_json_object(raw) == '{"a": 1}'


def test_extract_json_object_strips_a_bare_fence():
    raw = '```\n{"a": 1}\n```'
    assert extract_json_object(raw) == '{"a": 1}'


def test_extract_json_object_strips_leading_and_trailing_prose():
    raw = 'Here is the extraction:\n\n{"a": 1}\n\nHope that helps!'
    assert extract_json_object(raw) == '{"a": 1}'


def test_extract_json_object_is_not_confused_by_braces_inside_strings():
    raw = 'Sure: {"note": "the schema is {a, b, c}"}'
    assert extract_json_object(raw) == '{"note": "the schema is {a, b, c}"}'


def test_extract_json_object_handles_stray_trailing_junk_after_a_complete_object():
    raw = '{"a": 1}\n```'
    assert extract_json_object(raw) == '{"a": 1}'


def test_extract_json_object_returns_input_unchanged_with_no_opening_brace():
    assert extract_json_object("no json here") == "no json here"


# --- create_json_message -----------------------------------------------------


class _TextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text: str):
        self.content = [_TextBlock(text)]


class _SequencedMessages:
    """Returns each of `responses` in turn, one per .create() call, and
    records the kwargs of every call so tests can assert on the
    conversation each attempt actually sent."""

    def __init__(self, responses: list[str]):
        self._responses = iter(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeMessage(next(self._responses))


class _SequencedClient:
    def __init__(self, responses: list[str]):
        self.messages = _SequencedMessages(responses)


def test_create_json_message_sends_messages_unchanged_and_parses_in_one_call():
    """No assistant-message prefill — some Claude models reject it
    outright ("the conversation must end with a user message"), so the
    messages list handed to the SDK must be exactly what the caller
    passed in, still ending with that same user turn."""
    client = _SequencedClient(['{"a": 1}'])

    result = create_json_message(
        client,
        _DomainError,
        model="m",
        max_tokens=10,
        system="s",
        messages=[{"role": "user", "content": "hi"}],
    )

    assert result == {"a": 1}
    assert len(client.messages.calls) == 1
    assert client.messages.calls[0]["messages"] == [{"role": "user", "content": "hi"}]
    assert "temperature" not in client.messages.calls[0]


def test_create_json_message_strips_a_markdown_fence_around_the_response():
    client = _SequencedClient(['```json\n{"a": 1}\n```'])

    result = create_json_message(
        client,
        _DomainError,
        model="m",
        max_tokens=10,
        system="s",
        messages=[{"role": "user", "content": "hi"}],
    )

    assert result == {"a": 1}


def test_create_json_message_retries_once_with_a_correction_then_succeeds():
    client = _SequencedClient(["not json at all", '{"a": 1}'])

    result = create_json_message(
        client,
        _DomainError,
        model="m",
        max_tokens=10,
        system="s",
        messages=[{"role": "user", "content": "hi"}],
    )

    assert result == {"a": 1}
    assert len(client.messages.calls) == 2
    retry_messages = client.messages.calls[1]["messages"]
    # a completed assistant turn followed by a new user turn — ordinary
    # multi-turn history, not prefill — so the retry still ends in "user"
    assert retry_messages[-1]["role"] == "user"
    assert "Return ONLY the raw JSON object" in retry_messages[-1]["content"]
    assert retry_messages[-2] == {"role": "assistant", "content": "not json at all"}


def test_create_json_message_raises_the_domain_error_after_both_attempts_fail():
    client = _SequencedClient(["still not json", "still not json either"])

    with pytest.raises(_DomainError) as excinfo:
        create_json_message(
            client,
            _DomainError,
            model="m",
            max_tokens=10,
            system="s",
            messages=[{"role": "user", "content": "hi"}],
        )

    assert "after a retry" in str(excinfo.value)
    assert len(client.messages.calls) == 2

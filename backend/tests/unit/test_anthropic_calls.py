"""services/ai/anthropic_calls.py is the one place every Anthropic-backed
provider (extraction, composition, predicate_assist, diff_note) routes
its SDK call through — these tests pin that a missing/invalid key or a
connection failure always comes out as the caller's own domain error
with a clear, human-readable message, never a raw SDK exception, and
that structured output goes through forced tool use rather than
free-text JSON the model might emit malformed."""

import httpx
import pytest
from anthropic import APIConnectionError, APIStatusError, AuthenticationError

from services.ai.anthropic_calls import create_message, create_tool_message


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


# --- create_tool_message -----------------------------------------------------


class _ToolUseBlock:
    def __init__(self, name: str, tool_input: dict):
        self.type = "tool_use"
        self.name = name
        self.input = tool_input


class _TextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, content: list):
        self.content = content


class _SequencedMessages:
    """Returns each of `responses` (each a list of content blocks) in
    turn, one per .create() call, and records the kwargs of every call
    so tests can assert on exactly what each attempt sent."""

    def __init__(self, responses: list[list]):
        self._responses = iter(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeMessage(next(self._responses))


class _SequencedClient:
    def __init__(self, responses: list[list]):
        self.messages = _SequencedMessages(responses)


def _call_tool_message(client, **overrides):
    kwargs = {
        "model": "m",
        "max_tokens": 10,
        "system": "s",
        "messages": [{"role": "user", "content": "hi"}],
        "tool_name": "my_tool",
        "tool_description": "records the thing",
        "input_schema": {"type": "object", "properties": {"a": {"type": "integer"}}},
    }
    kwargs.update(overrides)
    return create_tool_message(client, _DomainError, **kwargs)


def test_create_tool_message_returns_the_tool_input_in_one_call():
    client = _SequencedClient([[_ToolUseBlock("my_tool", {"a": 1})]])

    result = _call_tool_message(client)

    assert result == {"a": 1}
    assert len(client.messages.calls) == 1
    call = client.messages.calls[0]
    assert call["messages"] == [{"role": "user", "content": "hi"}]
    assert call["tools"] == [
        {
            "name": "my_tool",
            "description": "records the thing",
            "input_schema": {"type": "object", "properties": {"a": {"type": "integer"}}},
        }
    ]
    assert call["tool_choice"] == {"type": "tool", "name": "my_tool"}
    assert "temperature" not in call


def test_create_tool_message_ignores_other_content_blocks():
    client = _SequencedClient([[_TextBlock("thinking..."), _ToolUseBlock("my_tool", {"a": 1})]])

    result = _call_tool_message(client)

    assert result == {"a": 1}


def test_create_tool_message_retries_once_then_succeeds():
    client = _SequencedClient([[], [_ToolUseBlock("my_tool", {"a": 1})]])

    result = _call_tool_message(client)

    assert result == {"a": 1}
    assert len(client.messages.calls) == 2
    retry_messages = client.messages.calls[1]["messages"]
    assert retry_messages[0] == {"role": "user", "content": "hi"}
    assert retry_messages[-1]["role"] == "user"
    assert "my_tool" in retry_messages[-1]["content"]


def test_create_tool_message_raises_the_domain_error_after_both_attempts_fail():
    client = _SequencedClient([[], []])

    with pytest.raises(_DomainError) as excinfo:
        _call_tool_message(client)

    assert "after a retry" in str(excinfo.value)
    assert len(client.messages.calls) == 2


def test_create_tool_message_ignores_a_tool_use_block_for_a_different_tool():
    client = _SequencedClient(
        [[_ToolUseBlock("some_other_tool", {"x": 1})], [_ToolUseBlock("some_other_tool", {"x": 1})]]
    )

    with pytest.raises(_DomainError):
        _call_tool_message(client)

    assert len(client.messages.calls) == 2

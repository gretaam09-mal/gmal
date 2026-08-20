"""Reproduces the actual reported bug against the real provider code path:
P-COMPOSE nesting its output under an extra "prose" key instead of the
flat ComposedMemoProse shape, which made memo composition fail with
"3 validation errors for ComposedMemoProse — headline_summary / obligations
/ excluded_summary — Field required." Proves the fix at the level Anthropic
actually enforces it — the request AnthropicCompositionProvider sends now
declares strict:true with additionalProperties:false on every object in
the schema, so the API is contractually guaranteed to reject anything but
the exact declared shape — and that a well-formed tool response still
composes end to end with all three fields present.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from services.composition.anthropic_provider import AnthropicCompositionProvider
from services.composition.context import MemoComposeContext, ObligationComposeInput
from services.composition.provider import CompositionError


class _ToolUseBlock:
    def __init__(self, name: str, tool_input: dict):
        self.type = "tool_use"
        self.name = name
        self.input = tool_input


class _FakeMessage:
    def __init__(self, content: list):
        self.content = content


class _RecordingMessages:
    def __init__(self, response_content: list):
        self._response_content = response_content
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeMessage(self._response_content)


class _FakeClient:
    def __init__(self, response_content: list):
        self.messages = _RecordingMessages(response_content)


_GOOD_INPUT = {
    "headline_summary": "This deal carries a bounded, quantified regulatory exposure.",
    "obligations": [
        {
            "predicate_id": "pred-1",
            "what_it_requires": "Appoint a data protection officer.",
            "why_it_applies": "The target processes personal data at scale.",
        }
    ],
    "excluded_summary": "No obligations were excluded from this analysis.",
}


def _context() -> MemoComposeContext:
    return MemoComposeContext(
        headline_low=Decimal("20000"),
        headline_likely=Decimal("25000"),
        headline_high=Decimal("32500"),
        currency="GBP",
        confidence_grade="B",
        binding_obligations=(
            ObligationComposeInput(
                predicate_id="pred-1",
                obligation_summary="Appoint a DPO.",
                outcome="binds",
                rationale="Binds: processes personal data.",
                clause_texts=("A firm must appoint a DPO.",),
                clause_refs=("s.1",),
                impact_low=Decimal("20000"),
                impact_likely=Decimal("25000"),
                impact_high=Decimal("32500"),
                currency="GBP",
            ),
        ),
        excluded_obligations=(),
    )


def _provider_with_fake_client(response_content: list) -> AnthropicCompositionProvider:
    provider = AnthropicCompositionProvider(api_key="test-key")
    provider._client = _FakeClient(response_content)
    return provider


def test_declares_the_schema_strict_so_the_api_cannot_nest_the_payload_under_an_extra_key():
    provider = _provider_with_fake_client(
        [_ToolUseBlock("record_composed_memo_prose", _GOOD_INPUT)]
    )

    provider.compose(_context())

    call = provider._client.messages.calls[0]
    tool = call["tools"][0]
    assert tool["strict"] is True
    schema = tool["input_schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"headline_summary", "obligations", "excluded_summary"}
    # The nested per-obligation object is just as locked down — this is
    # exactly the level a {"prose": {...}} wrapper around one obligation,
    # rather than the whole payload, would have needed to slip past.
    obligation_schema = schema["$defs"]["ComposedObligationProse"]
    assert obligation_schema["additionalProperties"] is False


def test_composes_end_to_end_with_all_three_fields_present_given_a_well_formed_tool_response():
    """The end-to-end acceptance check the bug report asked for: given a
    tool_use.input that matches ComposedMemoProse exactly — what strict
    mode now guarantees rather than merely hopes for — .compose() returns
    a result with headline_summary, the per-obligation prose, and
    excluded_summary all populated. The memo can actually compose."""
    provider = _provider_with_fake_client(
        [_ToolUseBlock("record_composed_memo_prose", _GOOD_INPUT)]
    )

    prose = provider.compose(_context())

    assert prose.headline_summary == _GOOD_INPUT["headline_summary"]
    assert prose.obligations[0].what_it_requires == "Appoint a data protection officer."
    assert prose.obligations[0].why_it_applies == "The target processes personal data at scale."
    assert prose.excluded_summary == _GOOD_INPUT["excluded_summary"]


def test_a_nested_prose_wrapper_still_fails_clearly_if_it_ever_slipped_through():
    """Defense in depth: even though strict mode makes this shape
    contractually impossible for Anthropic to return, a nested wrapper
    must still fail loudly naming the missing fields — never silently
    compose a broken memo. This is the exact shape and message from the
    original bug report."""
    provider = _provider_with_fake_client(
        [
            _ToolUseBlock(
                "record_composed_memo_prose",
                {"prose": _GOOD_INPUT},
            )
        ]
    )

    with pytest.raises(CompositionError) as excinfo:
        provider.compose(_context())

    message = str(excinfo.value)
    assert "P-COMPOSE output failed validation" in message
    assert "headline_summary" in message
    assert "obligations" in message
    assert "excluded_summary" in message

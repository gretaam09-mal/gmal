"""Shared by every Anthropic-backed provider (services/extraction,
services/composition, services/predicate_assist, services/diff_note):
one place that turns the Anthropic SDK's own exceptions into each
provider's domain error, with a message a non-engineer reviewer can act
on. Without this, a missing or invalid PROVISION_ANTHROPIC_API_KEY (or a
transient outage) raises a raw SDK exception that no route catches,
which FastAPI turns into an opaque 500 — exactly what CONVENTIONS.md's
fail-closed-with-a-clear-error expectation rules out.

This is also the one place every one of those four providers gets
schema-shaped structured output from the model. Earlier versions of this
module asked the model to emit JSON as plain text and recovered it
afterwards (stripping markdown fences, scanning for balanced braces,
retrying with a correction) — but that only ever reduces how often the
model's free text fails to parse, it can't eliminate it: a model can
still emit an unclosed brace or a truncated string in the middle of
prose generation, and no amount of after-the-fact recovery fixes JSON
that was never well-formed to begin with.

create_tool_message replaces that approach with Anthropic tool use:
the caller's schema is declared as a tool, tool_choice forces the model
to answer through exactly that tool call, and the API constructs the
`input` payload itself from constrained, schema-guided generation — so
the well-formedness class of failure (mismatched braces, truncated
strings) cannot happen. There is no text to parse; `.input` on the
resulting tool_use block is already a dict.

Every request built here still uses the plain, universal request shape
otherwise: no `temperature` (or other sampling parameter) and no
assistant-message prefill — some Claude models reject one or both of
those outright, as this codebase learned from two separate live 400s.
tools/tool_choice, by contrast, are core Messages API features every
current Claude model supports, so adding them doesn't reintroduce that
problem.
"""
from __future__ import annotations

from typing import Any, TypeVar

import anthropic

_ErrorT = TypeVar("_ErrorT", bound=Exception)


def create_message(
    client: anthropic.Anthropic, error_cls: type[_ErrorT], **kwargs: Any
) -> anthropic.types.Message:
    """client.messages.create(**kwargs), with SDK exceptions translated
    into error_cls (the caller's own *Error, e.g. ExtractionError) so a
    single try/except in the route catches every failure mode the same
    way, whether it's "no key configured", "key rejected", or "couldn't
    reach the API"."""
    try:
        return client.messages.create(**kwargs)
    except anthropic.AuthenticationError as exc:
        raise error_cls(
            "The Anthropic API rejected the configured key — check that "
            "PROVISION_ANTHROPIC_API_KEY is set to a valid key."
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise error_cls(f"Could not reach the Anthropic API: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise error_cls(
            f"The Anthropic API returned an error (status {exc.status_code}): {exc.message}"
        ) from exc
    except anthropic.APIError as exc:
        raise error_cls(f"The Anthropic API request failed: {exc}") from exc


def _find_tool_input(response: anthropic.types.Message, tool_name: str) -> dict[str, Any] | None:
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    return None


def create_tool_message(
    client: anthropic.Anthropic,
    error_cls: type[_ErrorT],
    *,
    model: str,
    max_tokens: int,
    system: str,
    messages: list[dict[str, Any]],
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
) -> dict[str, Any]:
    """Structured-output call: declares (tool_name, tool_description,
    input_schema) as the model's one available tool and forces the
    response through it (tool_choice pins the specific tool, so there's
    no ambiguity about whether — or which — tool to call). Returns
    tool_use.input directly — already a parsed dict, schema-guided by
    the API, never free text this module has to recover JSON from.

    Retries once, with a plain follow-up user turn, if the model still
    doesn't produce a usable call to that tool (e.g. generation cut off
    by max_tokens before the tool call completed) — ordinary multi-turn
    history, not assistant-message prefill, so every model accepts it.
    Raises error_cls if both attempts fail.
    """
    tool = {"name": tool_name, "description": tool_description, "input_schema": input_schema}
    tool_choice = {"type": "tool", "name": tool_name}

    def _attempt(attempt_messages: list[dict[str, Any]]) -> dict[str, Any] | None:
        response = create_message(
            client,
            error_cls,
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=attempt_messages,
            tools=[tool],
            tool_choice=tool_choice,
        )
        return _find_tool_input(response, tool_name)

    result = _attempt(messages)
    if result is not None:
        return result

    retry_messages = [
        *messages,
        {
            "role": "user",
            "content": (
                f"Your previous response did not produce a complete call to the "
                f"{tool_name} tool. Please call it again with the complete data."
            ),
        },
    ]
    result = _attempt(retry_messages)
    if result is not None:
        return result

    raise error_cls(f"Model did not produce a valid {tool_name} tool call after a retry.")

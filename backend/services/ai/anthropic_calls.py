"""Shared by every Anthropic-backed provider (services/extraction,
services/composition, services/predicate_assist, services/diff_note):
one place that turns the Anthropic SDK's own exceptions into each
provider's domain error, with a message a non-engineer reviewer can act
on. Without this, a missing or invalid PROVISION_ANTHROPIC_API_KEY (or a
transient outage) raises a raw SDK exception that no route catches,
which FastAPI turns into an opaque 500 — exactly what CONVENTIONS.md's
fail-closed-with-a-clear-error expectation rules out.

This is also the one place that turns a model's raw text response into a
parsed JSON object for every one of those four prompts, all of which
share the same contract: "respond with exactly one JSON object, nothing
else." Models occasionally break that contract anyway — wrapping the
object in a ```json fence, or adding a sentence of preamble/trailing
commentary — despite every prompt explicitly asking for raw JSON. See
create_json_message for the defence.
"""
from __future__ import annotations

import json
import re
from typing import Any, TypeVar

import anthropic

_ErrorT = TypeVar("_ErrorT", bound=Exception)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


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


def _response_text(response: anthropic.types.Message) -> str:
    return "".join(block.text for block in response.content if block.type == "text")


def extract_json_object(raw: str) -> str:
    """Best-effort recovery of a single JSON object from a model's raw
    text response: strips a ```json / ``` markdown fence if present, then
    scans for the outermost balanced {...} to drop any leading or
    trailing prose the model added around it. Brace-matching is
    string-aware (a '{' or '}' inside a quoted JSON string doesn't count)
    so prose *inside* the object's own string values can't confuse it.

    Returns the input unchanged (trimmed) if no '{' is found at all, so
    a caller's own json.loads still fails with a sensible error instead
    of this silently returning something else.
    """
    text = raw.strip()
    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]  # unbalanced (e.g. truncated at max_tokens) — let json.loads raise


def _try_parse_json_call(
    client: anthropic.Anthropic,
    error_cls: type[_ErrorT],
    *,
    model: str,
    max_tokens: int,
    system: str,
    messages: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    """One call attempt: prefills the assistant turn with "{" — Anthropic's
    documented technique for suppressing a markdown-fenced or
    prose-wrapped response, since the model's continuation is forced to
    start mid-object and so can't open with a ```json fence — then
    extracts and parses the result. Returns (None, raw) on failure so the
    caller can decide whether to retry or give up, without losing the
    raw text for the error message either way.
    """
    prefilled_messages = [*messages, {"role": "assistant", "content": "{"}]
    response = create_message(
        client,
        error_cls,
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=prefilled_messages,
    )
    raw = "{" + _response_text(response)
    try:
        return json.loads(extract_json_object(raw)), raw
    except json.JSONDecodeError:
        return None, raw


def create_json_message(
    client: anthropic.Anthropic,
    error_cls: type[_ErrorT],
    *,
    model: str,
    max_tokens: int,
    system: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """For the shared "respond with exactly one JSON object" contract
    every P-EXTRACT/P-PREDICATE-ASSIST/P-COMPOSE/P-DIFF-NOTE call makes.
    Guards the whole class of "model didn't return clean JSON" failures:

    1. Prefills the assistant turn with "{" on every attempt (see
       _try_parse_json_call) so the model can't wrap the object in a
       markdown fence in the first place.
    2. If the result still isn't parseable (fenced/prose-wrapped despite
       the prefill, or truncated), retries once with the failed output
       fed back and an explicit "return ONLY the raw JSON object" and
       tries again.
    3. Raises error_cls with a clear message (including a snippet of the
       unparseable output) if both attempts fail, rather than letting a
       raw json.JSONDecodeError escape.

    Returns the parsed dict — callers still run their own Pydantic
    model_validate on it, so schema validation is unchanged.
    """
    parsed, raw = _try_parse_json_call(
        client, error_cls, model=model, max_tokens=max_tokens, system=system, messages=messages
    )
    if parsed is not None:
        return parsed

    correction = (
        f"Your previous response could not be parsed as JSON: {raw!r}\n\n"
        "Return ONLY the raw JSON object — no markdown code fences, no "
        "explanation, and no text before or after it."
    )
    retry_messages = [
        *messages,
        {"role": "assistant", "content": raw},
        {"role": "user", "content": correction},
    ]
    parsed, raw = _try_parse_json_call(
        client,
        error_cls,
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=retry_messages,
    )
    if parsed is not None:
        return parsed

    raise error_cls(f"Model did not return valid JSON after a retry: {raw!r}")

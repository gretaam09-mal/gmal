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

Every request built here uses the plain, universally-supported Messages
API shape: `system` + a `messages` list that always ends with a `user`
turn, and no parameter beyond `model`/`max_tokens`/`system`/`messages`.
Two things this deliberately avoids, both because Claude models differ
on whether they accept them (as this codebase learned the hard way from
two separate live 400s): a `temperature` (or other sampling) parameter,
and assistant-message prefill (ending `messages` with a partial
`assistant` turn for the model to continue) — some models reject prefill
outright ("the conversation must end with a user message"). Robustness
against fenced/prose-wrapped JSON instead comes entirely from the prompt
text plus extract_json_object's recovery below, which works against any
model's plain-text output.
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
    """One call attempt: calls the model with `messages` exactly as given
    (must already end with a `user` turn — no assistant prefill), then
    extracts and parses the result. Returns (None, raw) on failure so the
    caller can decide whether to retry or give up, without losing the
    raw text for the error message either way.
    """
    response = create_message(
        client,
        error_cls,
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    raw = _response_text(response)
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
    Guards the whole class of "model didn't return clean JSON" failures,
    using only the plain, universally-supported request shape (no
    assistant prefill, no temperature — see the module docstring):

    1. Calls the model with `messages` as given and runs the response
       through extract_json_object (strips a markdown fence and any
       leading/trailing prose, then parses the recovered object).
    2. If that isn't parseable (still fenced/prose-wrapped, or
       truncated), retries once: the failed output is fed back as a
       completed assistant turn, followed by a new user turn asking
       explicitly for "the raw JSON object, no markdown code fences, no
       explanation" — a normal multi-turn exchange, not prefill, so
       every model accepts it.
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

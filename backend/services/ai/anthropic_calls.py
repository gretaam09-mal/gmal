"""Shared by every Anthropic-backed provider (services/extraction,
services/composition, services/predicate_assist, services/diff_note):
one place that turns the Anthropic SDK's own exceptions into each
provider's domain error, with a message a non-engineer reviewer can act
on. Without this, a missing or invalid PROVISION_ANTHROPIC_API_KEY (or a
transient outage) raises a raw SDK exception that no route catches,
which FastAPI turns into an opaque 500 — exactly what CONVENTIONS.md's
fail-closed-with-a-clear-error expectation rules out.
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

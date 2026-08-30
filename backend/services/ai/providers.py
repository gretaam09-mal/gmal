"""The provider abstraction every AI vendor integration implements, and
the confidentiality gate every one of them is checked against before a
network call is made — see docs/Provision_Kimi_Integration_Spec.md
section 2-3. Callers never talk to a vendor SDK/HTTP client directly;
they go through services/ai/router.py, which resolves one of these.
"""
from __future__ import annotations

from typing import Any, Literal, Protocol, TypeVar

from services.ai.errors import ConfidentialRoutingError

DataClass = Literal["public", "confidential"]

_ErrorT = TypeVar("_ErrorT", bound=Exception)


class AIProvider(Protocol):
    """One vendor integration. name/confidential_ok/models/supports_structured
    are plain metadata the router and its config validation read; the two
    generate_* methods are the only way a caller reaches the vendor."""

    name: str
    confidential_ok: bool
    models: tuple[str, ...]
    supports_structured: bool

    def generate_structured(
        self,
        error_cls: type[_ErrorT],
        *,
        model: str | None,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        tool_name: str,
        tool_description: str,
        input_schema: dict[str, Any],
        strict: bool = True,
    ) -> dict[str, Any]:
        """Returns a dict shaped by input_schema — never free text this
        caller has to parse. Raises error_cls (never a raw vendor SDK/HTTP
        exception) on any failure: missing/invalid key, transport error,
        or output that doesn't validate against the schema after the
        provider's own retry.

        strict=True (default) asks the vendor to *guarantee* the result
        matches input_schema exactly (see services/ai/strict_schema.py).
        Pass strict=False only when input_schema itself can't be made
        strict-safe — e.g. a field that's deliberately an open-ended dict
        with no fixed shape (see services/predicate_assist, whose
        predicate expression tree strict mode's additionalProperties:
        false-everywhere rule could only express as {}); that caller
        relies on its own post-validation instead."""
        ...

    def generate_text(
        self,
        error_cls: type[_ErrorT],
        *,
        model: str | None,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
    ) -> str:
        """Free-text generation — no schema, no tool use. Nothing in this
        codebase's current five AI calls needs this (every one of them
        wants structured output); it exists because
        docs/Provision_Kimi_Integration_Spec.md section 2 specifies it as
        part of the provider interface, for whichever future task turns
        out not to need a schema."""
        ...


def ensure_data_class_allowed(provider: AIProvider, data_class: DataClass) -> None:
    """The confidentiality gate itself: a data_class="confidential" call
    must never reach a provider that isn't confidential_ok. A pure,
    dependency-free check — no client, no I/O — so calling it can never
    itself make a network call, which is what lets a test prove "raises
    before any network call" without needing to spy on a client at all.
    AIRouter calls this immediately before invoking a resolved provider,
    for every call, regardless of what AI_ROUTING's own data_class says
    (see services/ai/routing.py::validate_routing for the config-time
    version of this same rule)."""
    if data_class == "confidential" and not provider.confidential_ok:
        raise ConfidentialRoutingError(
            f"Refusing to send a confidential call to provider {provider.name!r} — "
            f"it is not confidential_ok. See "
            f"docs/Provision_Kimi_Integration_Spec.md section 0."
        )

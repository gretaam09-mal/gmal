"""Errors owned by the AI router itself (services/ai/router.py), distinct
from each domain's own *Error (ExtractionError, CompositionError, ...).
Those still fire for a failed *call* (bad key, network outage, invalid
output) via the error_cls each domain passes into the router — see
services/ai/providers.py::AIProvider.generate_structured. These two exist
for failures that are about *routing itself*, before a domain's own error
handling is even reachable.
"""
from __future__ import annotations


class AIRoutingConfigError(Exception):
    """Raised when AI_ROUTING (services/ai/routing.py) is internally
    inconsistent — e.g. a task tagged data_class="confidential" names a
    primary or fallback provider that isn't confidential_ok. Raised at
    AIRouter construction (see services/ai/router.py::AIRouter.__init__),
    so a bad config fails at process start / first use, never silently at
    the moment a real client call happens to hit that task."""


class ConfidentialRoutingError(Exception):
    """Raised the moment a data_class="confidential" call would be sent to
    a provider whose confidential_ok is False — before any network call
    reaches that provider. This is Provision's core AI trust rule made
    into code: no client deal material may reach a provider that trains
    on submitted content or lacks a no-training DPA (see
    docs/Provision_Kimi_Integration_Spec.md section 0). Every provider
    resolution in AIRouter.generate_structured/generate_text checks this
    before calling out, regardless of what AI_ROUTING says — config
    validation (AIRoutingConfigError) is the first line of defence, this
    is the second, applied to the specific call actually being made."""

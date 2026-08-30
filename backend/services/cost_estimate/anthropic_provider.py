"""The real P-COST-ESTIMATE provider — routes through the multi-provider
AI layer (services/ai/router.py). See services/composition/
anthropic_provider.py for the identical fail-closed-without-a-key shape
and why this is never exercised by this repo's tests.

P-COST-ESTIMATE scales a company-specific figure to a real target's
profile — data_class="confidential" (docs/Provision_Kimi_Integration_Spec.md
section 1's "cost estimation" task). The router's "cost_estimation" task
never has a Kimi-hosted candidate; this always uses Claude, at the
strongest configured model (CONVENTIONS.md rule 1's narrow cost-estimation
exception), regardless of anything Kimi-related.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from api.config import get_settings
from services.ai.router import AIRouter, get_ai_router
from services.cost_estimate.context import CostEstimateContext
from services.cost_estimate.provider import CostEstimateError
from services.cost_estimate.schemas import CostEstimate

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "ai" / "prompts" / "P-COST-ESTIMATE.v1.md"

_TOOL_NAME = "record_cost_estimate"
_TOOL_DESCRIPTION = (
    "Records the company-specific best/likely/worst GBP cost estimate, its "
    "cost drivers, assumptions, and rationale."
)


class CostEstimateNotConfiguredError(CostEstimateError):
    """Raised when no Anthropic API key is configured yet."""


def _load_system_prompt() -> str:
    text = _PROMPT_PATH.read_text()
    marker = "## System prompt\n\n```\n"
    start = text.index(marker) + len(marker)
    end = text.index("\n```", start)
    return text[start:end]


def _render_user_message(context: CostEstimateContext) -> str:
    facts = "\n".join(f"- {fact.label}: {fact.value}" for fact in context.company_facts) or (
        "- (no profile facts recorded yet)"
    )
    clause_text = "\n".join(context.clause_texts)
    return (
        f"Obligation: {context.obligation_summary}\n"
        f"Why it binds: {context.rationale}\n"
        f"Clause references: {', '.join(context.clause_refs)}\n"
        f"Clause text: {clause_text}\n\n"
        f"Company profile facts:\n{facts}"
    )


class AnthropicCostEstimateProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        router: AIRouter | None = None,
    ) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.anthropic_api_key
        if not key:
            raise CostEstimateNotConfiguredError("PROVISION_ANTHROPIC_API_KEY is not set")
        self._model = model or settings.anthropic_cost_estimate_model
        self._system_prompt = _load_system_prompt()
        self._router = router or get_ai_router()

    def estimate(
        self,
        context: CostEstimateContext,
        *,
        session: Session | None = None,
        tenant_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> CostEstimate:
        data = self._router.generate_structured(
            "cost_estimation",
            CostEstimateError,
            data_class="confidential",
            max_tokens=2048,
            system=self._system_prompt,
            messages=[{"role": "user", "content": _render_user_message(context)}],
            tool_name=_TOOL_NAME,
            tool_description=_TOOL_DESCRIPTION,
            input_schema=CostEstimate.model_json_schema(),
            model_overrides={"claude": self._model},
            session=session,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        try:
            return CostEstimate.model_validate(data)
        except ValidationError as exc:
            raise CostEstimateError(f"P-COST-ESTIMATE output failed validation: {exc}") from exc

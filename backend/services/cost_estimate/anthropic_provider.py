"""The real P-COST-ESTIMATE provider — see services/composition/
anthropic_provider.py for the identical fail-closed-without-a-key shape
and why this is never exercised by this repo's tests.
"""

from __future__ import annotations

from pathlib import Path

from anthropic import Anthropic
from pydantic import ValidationError

from api.config import get_settings
from services.ai.anthropic_calls import create_tool_message
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
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.anthropic_api_key
        if not key:
            raise CostEstimateNotConfiguredError("PROVISION_ANTHROPIC_API_KEY is not set")
        self._client = Anthropic(api_key=key)
        self._model = model or settings.anthropic_cost_estimate_model
        self._system_prompt = _load_system_prompt()

    def estimate(self, context: CostEstimateContext) -> CostEstimate:
        data = create_tool_message(
            self._client,
            CostEstimateError,
            model=self._model,
            max_tokens=2048,
            system=self._system_prompt,
            messages=[{"role": "user", "content": _render_user_message(context)}],
            tool_name=_TOOL_NAME,
            tool_description=_TOOL_DESCRIPTION,
            input_schema=CostEstimate.model_json_schema(),
        )
        try:
            return CostEstimate.model_validate(data)
        except ValidationError as exc:
            raise CostEstimateError(f"P-COST-ESTIMATE output failed validation: {exc}") from exc

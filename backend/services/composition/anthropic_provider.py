"""The real P-COMPOSE provider — routes through the multi-provider AI
layer (services/ai/router.py). Never exercised by this repo's tests (see
fixture_provider.py for what tests use instead); only reached when
PROVISION_ANTHROPIC_API_KEY is configured (api/deps.py falls back to
raising CompositionNotConfiguredError, mirroring how services/extraction
fails closed without a key).

P-COMPOSE writes prose about one client's target company — data_class=
"confidential" (see docs/Provision_Kimi_Integration_Spec.md section 1),
so the router's "memo_composition" task never has a Kimi-hosted candidate
at all; this call can never reach Kimi regardless of KIMI_ENABLED.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from api.config import get_settings
from services.ai.router import AIRouter, get_ai_router
from services.composition.context import MemoComposeContext, ObligationComposeInput
from services.composition.provider import CompositionError
from services.composition.schemas import ComposedMemoProse
from services.composition.validator import NumeralTraceabilityError, validate_composed_memo

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "ai" / "prompts" / "P-COMPOSE.v1.md"

_TOOL_NAME = "record_composed_memo_prose"
_TOOL_DESCRIPTION = (
    "Records the memo's narrative prose — headline summary, per-obligation "
    "what-it-requires/why-it-applies text, and the excluded-obligations summary."
)


class CompositionNotConfiguredError(CompositionError):
    """Raised when no Anthropic API key is configured yet."""


def _load_system_prompt() -> str:
    text = _PROMPT_PATH.read_text()
    marker = "## System prompt\n\n```\n"
    start = text.index(marker) + len(marker)
    end = text.index("\n```", start)
    return text[start:end]


def _format_money(value, currency: str) -> str:
    if value is None:
        return "n/a"
    return f"{currency} {value:,.2f}"


def _render_obligation(obligation: ObligationComposeInput) -> list[str]:
    lines = [
        f"- [{obligation.predicate_id}] {obligation.obligation_summary} "
        f"— reason: {obligation.rationale} "
        f"— clauses: {', '.join(obligation.clause_refs)} "
        f"— cost: best {_format_money(obligation.impact_low, obligation.currency)}, "
        f"likely {_format_money(obligation.impact_likely, obligation.currency)}, "
        f"worst {_format_money(obligation.impact_high, obligation.currency)}"
    ]
    for text in obligation.clause_texts:
        lines.append(f"  clause text: {text}")
    return lines


def _render_user_message(context: MemoComposeContext) -> str:
    lines = [
        f"Headline range: best {_format_money(context.headline_low, context.currency)}, "
        f"likely {_format_money(context.headline_likely, context.currency)}, "
        f"worst {_format_money(context.headline_high, context.currency)}.",
        f"Confidence grade: {context.confidence_grade}.",
        "",
        "Binding obligations:",
    ]
    for obligation in context.binding_obligations:
        lines.extend(_render_obligation(obligation))
    lines.append("")
    lines.append("Excluded obligations:")
    for obligation in context.excluded_obligations:
        lines.append(
            f"- [{obligation.predicate_id}] {obligation.obligation_summary} "
            f"— reason: {obligation.rationale}"
        )
    return "\n".join(lines)


class AnthropicCompositionProvider:
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
            raise CompositionNotConfiguredError("PROVISION_ANTHROPIC_API_KEY is not set")
        self._model = model or settings.anthropic_extraction_model
        self._system_prompt = _load_system_prompt()
        self._router = router or get_ai_router()

    def compose(
        self,
        context: MemoComposeContext,
        *,
        session: Session | None = None,
        tenant_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> ComposedMemoProse:
        data = self._router.generate_structured(
            "memo_composition",
            CompositionError,
            data_class="confidential",
            max_tokens=2048,
            system=self._system_prompt,
            messages=[{"role": "user", "content": _render_user_message(context)}],
            tool_name=_TOOL_NAME,
            tool_description=_TOOL_DESCRIPTION,
            input_schema=ComposedMemoProse.model_json_schema(),
            model_overrides={"claude": self._model},
            session=session,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        try:
            prose = ComposedMemoProse.model_validate(data)
        except ValidationError as exc:
            raise CompositionError(f"P-COMPOSE output failed validation: {exc}") from exc

        try:
            validate_composed_memo(prose, context)
        except NumeralTraceabilityError as exc:
            raise CompositionError(str(exc)) from exc
        return prose

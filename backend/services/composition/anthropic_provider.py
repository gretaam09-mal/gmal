"""The real P-COMPOSE provider — calls the Anthropic API. Never exercised
by this repo's tests (see fixture_provider.py for what tests use
instead); only reached when PROVISION_ANTHROPIC_API_KEY is configured
(api/deps.py falls back to raising CompositionNotConfiguredError,
mirroring how services/extraction fails closed without a key).
"""
from __future__ import annotations

import json
from pathlib import Path

from anthropic import Anthropic
from pydantic import ValidationError

from api.config import get_settings
from services.composition.context import MemoComposeContext, ObligationComposeInput
from services.composition.provider import CompositionError
from services.composition.schemas import ComposedMemoProse
from services.composition.validator import NumeralTraceabilityError, validate_composed_memo

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "ai" / "prompts" / "P-COMPOSE.v1.md"


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
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.anthropic_api_key
        if not key:
            raise CompositionNotConfiguredError("PROVISION_ANTHROPIC_API_KEY is not set")
        self._client = Anthropic(api_key=key)
        self._model = model or settings.anthropic_extraction_model
        self._system_prompt = _load_system_prompt()

    def compose(self, context: MemoComposeContext) -> ComposedMemoProse:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            temperature=0.0,
            system=self._system_prompt,
            messages=[{"role": "user", "content": _render_user_message(context)}],
        )
        raw = "".join(block.text for block in response.content if block.type == "text")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CompositionError(f"P-COMPOSE returned non-JSON output: {raw!r}") from exc
        try:
            prose = ComposedMemoProse.model_validate(data)
        except ValidationError as exc:
            raise CompositionError(f"P-COMPOSE output failed validation: {exc}") from exc

        try:
            validate_composed_memo(prose, context)
        except NumeralTraceabilityError as exc:
            raise CompositionError(str(exc)) from exc
        return prose

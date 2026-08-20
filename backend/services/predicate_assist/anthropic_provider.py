"""The real P-PREDICATE-ASSIST provider. See services/extraction/
anthropic_provider.py for the identical fail-closed-without-a-key shape
and why this is never exercised by this repo's tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from pydantic import ValidationError

from api.config import get_settings
from services.ai.anthropic_calls import create_tool_message
from services.predicate_assist.provider import PredicateAssistError
from services.predicate_assist.schemas import DraftedPredicate

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "ai" / "prompts" / "P-PREDICATE-ASSIST.v1.md"
)

_TOOL_NAME = "record_drafted_predicate"
_TOOL_DESCRIPTION = (
    "Records a draft predicate expression for a human reviewer to check and approve."
)


class PredicateAssistNotConfiguredError(PredicateAssistError):
    pass


def _load_system_prompt() -> str:
    text = _PROMPT_PATH.read_text()
    marker = "## System prompt\n\n```\n"
    start = text.index(marker) + len(marker)
    end = text.index("\n```", start)
    return text[start:end]


class AnthropicPredicateAssistProvider:
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.anthropic_api_key
        if not key:
            raise PredicateAssistNotConfiguredError("PROVISION_ANTHROPIC_API_KEY is not set")
        self._client = Anthropic(api_key=key)
        self._model = model or settings.anthropic_extraction_model
        self._system_prompt = _load_system_prompt()

    def draft(
        self,
        *,
        obligation_summary: str,
        who_value: str,
        who_clause_ref: str,
        threshold_value: str,
        threshold_clause_ref: str,
        available_fields: list[dict[str, Any]],
    ) -> DraftedPredicate:
        user_message = (
            f"Obligation: {obligation_summary}\n"
            f"Who it applies to: {who_value} (cited: {who_clause_ref})\n"
            f"Threshold: {threshold_value} (cited: {threshold_clause_ref})\n\n"
            f"Available profile fields:\n{json.dumps(available_fields)}"
        )
        data = create_tool_message(
            self._client,
            PredicateAssistError,
            model=self._model,
            max_tokens=1024,
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tool_name=_TOOL_NAME,
            tool_description=_TOOL_DESCRIPTION,
            input_schema=DraftedPredicate.model_json_schema(),
            # DraftedPredicate.expression is deliberately an open dict — the
            # predicate DSL tree has no fixed shape (see engine/predicates/dsl.py)
            # — so it can't be made additionalProperties:false like every other
            # schema in this codebase without collapsing it to {}. Anthropic's
            # strict tool use requires additionalProperties:false on every
            # object, with no exception, so strict mode isn't usable for this
            # one call; _must_be_valid_dsl below is what actually guards its shape.
            strict=False,
        )
        try:
            return DraftedPredicate.model_validate(data)
        except ValidationError as exc:
            raise PredicateAssistError(
                f"P-PREDICATE-ASSIST output failed validation: {exc}"
            ) from exc

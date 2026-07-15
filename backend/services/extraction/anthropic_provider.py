"""The real P-EXTRACT provider — calls the Anthropic API. Never exercised
by this repo's tests (see fixture_provider.py for what tests use
instead); only reached when PROVISION_ANTHROPIC_API_KEY is configured
(api/deps.py falls back to raising ExtractionNotConfiguredError, mirroring
how services/companies_house fails closed without a key).
"""

from __future__ import annotations

import json
from pathlib import Path

from anthropic import Anthropic
from pydantic import ValidationError

from api.config import get_settings
from services.ai.anthropic_calls import create_message
from services.extraction.provider import ExtractionError
from services.extraction.schemas import ExtractedObligation

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "ai" / "prompts" / "P-EXTRACT.v1.md"
)


class ExtractionNotConfiguredError(ExtractionError):
    """Raised when no Anthropic API key is configured yet — see
    docs/runbooks/ (extraction is optional infrastructure; the app and
    its tests run fine without it, same pattern as Companies House)."""


def _load_system_prompt() -> str:
    """Pulls the system prompt block out of the versioned markdown file so
    there's exactly one place the prompt text lives — not duplicated
    between the doc and the code."""
    text = _PROMPT_PATH.read_text()
    marker = "## System prompt\n\n```\n"
    start = text.index(marker) + len(marker)
    end = text.index("\n```", start)
    return text[start:end]


class AnthropicExtractionProvider:
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.anthropic_api_key
        if not key:
            raise ExtractionNotConfiguredError("PROVISION_ANTHROPIC_API_KEY is not set")
        self._client = Anthropic(api_key=key)
        self._model = model or settings.anthropic_extraction_model
        self._system_prompt = _load_system_prompt()

    def extract(
        self, *, clause_text: str, clause_ref: str, instrument_title: str
    ) -> ExtractedObligation:
        user_message = (
            f"Instrument: {instrument_title}\nClause {clause_ref}:\n\"\"\"\n{clause_text}\n\"\"\""
        )
        response = create_message(
            self._client,
            ExtractionError,
            model=self._model,
            max_tokens=1024,
            temperature=0.0,
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = "".join(block.text for block in response.content if block.type == "text")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"P-EXTRACT returned non-JSON output: {raw!r}") from exc
        try:
            return ExtractedObligation.model_validate(data)
        except ValidationError as exc:
            raise ExtractionError(f"P-EXTRACT output failed validation: {exc}") from exc

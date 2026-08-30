"""The real P-EXTRACT provider — routes through the multi-provider AI
layer (services/ai/router.py). Never exercised by this repo's tests (see
fixture_provider.py for what tests use instead); only reached when
PROVISION_ANTHROPIC_API_KEY is configured (api/deps.py falls back to
raising ExtractionNotConfiguredError, mirroring how services/companies_house
fails closed without a key).

P-EXTRACT is data_class="public" (see
docs/Provision_Kimi_Integration_Spec.md section 1 — it reads public
legislation text, never a client's own material), so this is the router's
"extraction" task: Kimi-primary, Claude-fallback, Kimi dark-launched
behind KIMI_ENABLED until it's cleared the golden-set gate. This class
still requires PROVISION_ANTHROPIC_API_KEY at construction, exactly as
before — the fallback has to always be usable regardless of Kimi's state.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from api.config import get_settings
from services.ai.router import AIRouter, get_ai_router
from services.extraction.provider import ExtractionError
from services.extraction.schemas import ExtractedObligation

_TOOL_NAME = "record_extracted_obligation"
_TOOL_DESCRIPTION = (
    "Records the single structured obligation extracted from the given clause."
)

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
            raise ExtractionNotConfiguredError("PROVISION_ANTHROPIC_API_KEY is not set")
        self._model = model or settings.anthropic_extraction_model
        self._system_prompt = _load_system_prompt()
        self._router = router or get_ai_router()

    def extract(
        self,
        *,
        clause_text: str,
        clause_ref: str,
        instrument_title: str,
        session: Session | None = None,
    ) -> ExtractedObligation:
        user_message = (
            f"Instrument: {instrument_title}\nClause {clause_ref}:\n\"\"\"\n{clause_text}\n\"\"\""
        )
        data = self._router.generate_structured(
            "extraction",
            ExtractionError,
            data_class="public",
            max_tokens=1024,
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tool_name=_TOOL_NAME,
            tool_description=_TOOL_DESCRIPTION,
            input_schema=ExtractedObligation.model_json_schema(),
            model_overrides={"claude": self._model},
            session=session,
        )
        try:
            return ExtractedObligation.model_validate(data)
        except ValidationError as exc:
            raise ExtractionError(f"P-EXTRACT output failed validation: {exc}") from exc

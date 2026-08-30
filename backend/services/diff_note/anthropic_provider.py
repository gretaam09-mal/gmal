"""The real P-DIFF-NOTE provider — routes through the multi-provider AI
layer (services/ai/router.py). See services/composition/anthropic_provider.py
for the identical fail-closed-without-a-key shape and why this is never
exercised by this repo's tests.

P-DIFF-NOTE summarises a diff between two versions of one client's memo —
data_class="confidential" (see docs/Provision_Kimi_Integration_Spec.md
section 0/1's principle: anything touching a client's deal inputs is
confidential, even though this specific task isn't in the spec's example
table). The router's "diff_note" task never has a Kimi-hosted candidate.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from api.config import get_settings
from engine.diff import Change
from services.ai.router import AIRouter, get_ai_router
from services.diff_note.provider import DiffNoteError
from services.diff_note.schemas import ComposedDiffNote
from services.diff_note.validator import validate_diff_note

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "ai" / "prompts" / "P-DIFF-NOTE.v1.md"

_TOOL_NAME = "record_diff_note"
_TOOL_DESCRIPTION = "Records the one-paragraph plain-English note explaining what changed."


class DiffNoteNotConfiguredError(DiffNoteError):
    """Raised when no Anthropic API key is configured yet."""


def _load_system_prompt() -> str:
    text = _PROMPT_PATH.read_text()
    marker = "## System prompt\n\n```\n"
    start = text.index(marker) + len(marker)
    end = text.index("\n```", start)
    return text[start:end]


def _format_value(value: object) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _render_user_message(changes: tuple[Change, ...]) -> str:
    lines = ["Changes:"]
    for change in changes:
        lines.append(
            f"- {change.field} ({change.kind.value}): before {_format_value(change.before)}, "
            f"after {_format_value(change.after)}, delta {_format_value(change.delta)}"
        )
    return "\n".join(lines)


class AnthropicDiffNoteProvider:
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
            raise DiffNoteNotConfiguredError("PROVISION_ANTHROPIC_API_KEY is not set")
        self._model = model or settings.anthropic_extraction_model
        self._system_prompt = _load_system_prompt()
        self._router = router or get_ai_router()

    def summarise(
        self,
        changes: tuple[Change, ...],
        *,
        session: Session | None = None,
        tenant_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> ComposedDiffNote:
        data = self._router.generate_structured(
            "diff_note",
            DiffNoteError,
            data_class="confidential",
            max_tokens=512,
            system=self._system_prompt,
            messages=[{"role": "user", "content": _render_user_message(changes)}],
            tool_name=_TOOL_NAME,
            tool_description=_TOOL_DESCRIPTION,
            input_schema=ComposedDiffNote.model_json_schema(),
            model_overrides={"claude": self._model},
            session=session,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        try:
            note = ComposedDiffNote.model_validate(data)
        except ValidationError as exc:
            raise DiffNoteError(f"P-DIFF-NOTE output failed validation: {exc}") from exc

        validate_diff_note(note, changes)
        return note

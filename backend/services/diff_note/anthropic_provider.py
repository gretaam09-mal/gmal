"""The real P-DIFF-NOTE provider — see services/composition/
anthropic_provider.py for the identical fail-closed-without-a-key shape
and why this is never exercised by this repo's tests.
"""
from __future__ import annotations

import json
from pathlib import Path

from anthropic import Anthropic
from pydantic import ValidationError

from api.config import get_settings
from engine.diff import Change
from services.diff_note.provider import DiffNoteError
from services.diff_note.schemas import ComposedDiffNote
from services.diff_note.validator import validate_diff_note

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "ai" / "prompts" / "P-DIFF-NOTE.v1.md"


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
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.anthropic_api_key
        if not key:
            raise DiffNoteNotConfiguredError("PROVISION_ANTHROPIC_API_KEY is not set")
        self._client = Anthropic(api_key=key)
        self._model = model or settings.anthropic_extraction_model
        self._system_prompt = _load_system_prompt()

    def summarise(self, changes: tuple[Change, ...]) -> ComposedDiffNote:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            temperature=0.0,
            system=self._system_prompt,
            messages=[{"role": "user", "content": _render_user_message(changes)}],
        )
        raw = "".join(block.text for block in response.content if block.type == "text")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DiffNoteError(f"P-DIFF-NOTE returned non-JSON output: {raw!r}") from exc
        try:
            note = ComposedDiffNote.model_validate(data)
        except ValidationError as exc:
            raise DiffNoteError(f"P-DIFF-NOTE output failed validation: {exc}") from exc

        validate_diff_note(note, changes)
        return note

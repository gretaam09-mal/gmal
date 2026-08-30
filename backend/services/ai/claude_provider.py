"""The "claude" entry in the provider registry (services/ai/router.py).
Thin adapter over services/ai/anthropic_calls.py's create_message/
create_tool_message — that module's structured-output behaviour (strict
tool use, retry-once, clean error translation) is unchanged by this file;
this only gives it the AIProvider shape the router expects.
"""
from __future__ import annotations

from typing import Any, TypeVar

import anthropic

from api.config import get_settings
from services.ai.anthropic_calls import create_message, create_tool_message

_ErrorT = TypeVar("_ErrorT", bound=Exception)


class ClaudeProvider:
    name = "claude"
    confidential_ok = True
    supports_structured = True

    def __init__(self, *, api_key: str | None = None, default_model: str | None = None) -> None:
        self._api_key = api_key
        self._default_model = default_model or get_settings().anthropic_extraction_model
        self.models = (self._default_model,)
        self._client: anthropic.Anthropic | None = None

    def _get_client(self, error_cls: type[_ErrorT]) -> anthropic.Anthropic:
        key = self._api_key if self._api_key is not None else get_settings().anthropic_api_key
        if not key:
            raise error_cls(
                "The Anthropic API rejected the configured key — check that "
                "PROVISION_ANTHROPIC_API_KEY is set to a valid key."
            )
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=key)
        return self._client

    def generate_structured(
        self,
        error_cls: type[_ErrorT],
        *,
        model: str | None,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        tool_name: str,
        tool_description: str,
        input_schema: dict[str, Any],
        strict: bool = True,
    ) -> dict[str, Any]:
        client = self._get_client(error_cls)
        return create_tool_message(
            client,
            error_cls,
            model=model or self._default_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tool_name=tool_name,
            tool_description=tool_description,
            input_schema=input_schema,
            strict=strict,
        )

    def generate_text(
        self,
        error_cls: type[_ErrorT],
        *,
        model: str | None,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
    ) -> str:
        client = self._get_client(error_cls)
        response = create_message(
            client,
            error_cls,
            model=model or self._default_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        for block in response.content:
            if block.type == "text":
                return block.text
        raise error_cls(f"Model {model or self._default_model} returned no text content.")

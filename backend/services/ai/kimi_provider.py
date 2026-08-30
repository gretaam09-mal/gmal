"""The "kimi" entry in the provider registry (services/ai/router.py) —
Moonshot's Kimi K3, OpenAI-compatible chat completions API. confidential_ok
= False: see docs/Provision_Kimi_Integration_Spec.md section 0 for why
(no documented training opt-out, no enterprise DPA, non-EU data
residency) — the router's confidentiality gate (services/ai/providers.py
::ensure_data_class_allowed) is what actually enforces that everywhere
this provider is reachable from; confidential_ok=False here is what that
gate reads.

Structured output uses response_format={"type": "json_schema", ...} per
the spec — the same declared schema Claude gets via strict tool use, just
carried through OpenAI's structured-output request shape instead of
Anthropic's tool-use shape. Implemented over a plain httpx.Client (this
codebase's existing HTTP dependency) rather than the openai SDK, so this
integration adds no new third-party dependency.
"""
from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx

from api.config import get_settings
from services.ai.strict_schema import prepare_strict_schema

_ErrorT = TypeVar("_ErrorT", bound=Exception)


def _extract_json_content(data: dict[str, Any]) -> dict[str, Any] | None:
    """Pulls the parsed JSON object out of a chat-completions response.
    Returns None (never raises) on anything that doesn't parse to a JSON
    object — the caller treats that as "no usable result yet" and retries
    once, same shape as create_tool_message's own retry-once behaviour."""
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if not content:
        return None
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


class KimiProvider:
    name = "kimi"
    confidential_ok = False
    supports_structured = True

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key
        self._base_url = (base_url or settings.moonshot_base_url).rstrip("/")
        self._default_model = default_model or settings.kimi_model
        self.models = (self._default_model,)
        # Injectable so tests never make a real HTTP call — see
        # tests/unit/test_kimi_provider.py.
        self._client = client

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self._base_url, timeout=60.0)
        return self._client

    def _auth_headers(self, error_cls: type[_ErrorT]) -> dict[str, str]:
        key = self._api_key if self._api_key is not None else get_settings().moonshot_api_key
        if not key:
            raise error_cls(
                "The Moonshot API key is not set — check that MOONSHOT_API_KEY "
                "is configured."
            )
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _post_chat_completion(
        self, body: dict[str, Any], error_cls: type[_ErrorT]
    ) -> dict[str, Any]:
        headers = self._auth_headers(error_cls)
        client = self._get_client()
        try:
            response = client.post("/chat/completions", json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise error_cls(f"The Moonshot API timed out: {exc}") from exc
        except httpx.RequestError as exc:
            raise error_cls(f"Could not reach the Moonshot API: {exc}") from exc

        if response.status_code == 401:
            raise error_cls(
                "The Moonshot API rejected the configured key — check that "
                "MOONSHOT_API_KEY is set to a valid key."
            )
        if response.status_code >= 400:
            raise error_cls(
                f"The Moonshot API returned an error (status {response.status_code}): "
                f"{response.text}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise error_cls(f"The Moonshot API returned a non-JSON response: {exc}") from exc

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
        chat_messages = [{"role": "system", "content": system}, *messages]
        resolved_model = model or self._default_model
        # Same strict-mode constraints as Claude's tool use (see
        # services/ai/strict_schema.py) — Moonshot's response_format is
        # OpenAI-compatible, and OpenAI-shaped strict JSON schema modes
        # share that additionalProperties:false-everywhere requirement.
        schema = prepare_strict_schema(input_schema) if strict else input_schema
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": tool_name, "schema": schema, "strict": strict},
        }

        def _attempt(attempt_messages: list[dict[str, Any]]) -> dict[str, Any] | None:
            data = self._post_chat_completion(
                {
                    "model": resolved_model,
                    "messages": attempt_messages,
                    "max_tokens": max_tokens,
                    "response_format": response_format,
                },
                error_cls,
            )
            return _extract_json_content(data)

        result = _attempt(chat_messages)
        if result is not None:
            return result

        retry_messages = [
            *chat_messages,
            {
                "role": "user",
                "content": (
                    f"Your previous response was not a valid JSON object matching the "
                    f"{tool_name!r} schema ({tool_description}). Respond again with only "
                    f"that JSON object."
                ),
            },
        ]
        result = _attempt(retry_messages)
        if result is not None:
            return result

        raise error_cls(
            f"Model {resolved_model} did not produce valid structured output for "
            f"{tool_name!r} after a retry."
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
        chat_messages = [{"role": "system", "content": system}, *messages]
        data = self._post_chat_completion(
            {
                "model": model or self._default_model,
                "messages": chat_messages,
                "max_tokens": max_tokens,
            },
            error_cls,
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise error_cls(f"Model {model or self._default_model} returned no content.") from exc
        if not content:
            raise error_cls(f"Model {model or self._default_model} returned no content.")
        return content

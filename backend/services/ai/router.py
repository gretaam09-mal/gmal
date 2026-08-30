"""The multi-provider AI layer's single entry point — every one of
Provision's five AI calls (P-EXTRACT, P-COMPOSE, P-PREDICATE-ASSIST,
P-DIFF-NOTE, P-COST-ESTIMATE) goes through AIRouter instead of talking to
a vendor SDK/HTTP client directly. See
docs/Provision_Kimi_Integration_Spec.md for the design this implements.

AIRouter.generate_structured is where the whole safety story lives:
- data_class is a required argument on every call (never inferred).
- Before any candidate provider is invoked, ensure_data_class_allowed
  checks it against that provider's confidential_ok — regardless of what
  AI_ROUTING says about the task, so a config bug can't be the only thing
  standing between a confidential call and a non-confidential_ok
  provider.
- AI_ROUTING itself is validated once, at construction (get_ai_router,
  the module-level singleton, does this the first time anything needs a
  router) — a confidential task naming a non-confidential_ok primary or
  fallback fails immediately, not the first time a real call happens to
  hit it.
- KIMI_ENABLED (api/config.py) dark-launches Kimi: off by default, a task
  whose primary is "kimi" transparently falls back to its next candidate
  while the flag is off, so turning Kimi on later is the only thing that
  changes behaviour.
- Every resolved call is logged to metrics_events (provider, model,
  data_class, task) — see services/ai/metrics.py.
"""
from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from api.config import get_settings
from services.ai.claude_provider import ClaudeProvider
from services.ai.errors import AIRoutingConfigError
from services.ai.kimi_provider import KimiProvider
from services.ai.metrics import record_ai_call
from services.ai.providers import AIProvider, DataClass, ensure_data_class_allowed
from services.ai.routing import AI_ROUTING, TaskRoute, validate_routing

_ErrorT = TypeVar("_ErrorT", bound=Exception)


def _dedupe(*names: str) -> list[str]:
    seen: list[str] = []
    for name in names:
        if name not in seen:
            seen.append(name)
    return seen


class AIRouter:
    def __init__(self, providers: dict[str, AIProvider], routing: dict[str, TaskRoute]) -> None:
        validate_routing(providers, routing)
        self._providers = providers
        self._routing = routing

    def _provider_for(self, name: str) -> AIProvider:
        provider = self._providers.get(name)
        if provider is None:
            raise AIRoutingConfigError(f"Unregistered AI provider {name!r}.")
        return provider

    def _route_for(self, task: str) -> TaskRoute:
        route = self._routing.get(task)
        if route is None:
            raise AIRoutingConfigError(
                f"No AI_ROUTING entry for task {task!r} — register it in "
                f"services/ai/routing.py before calling the router with it."
            )
        return route

    def generate_structured(
        self,
        task: str,
        error_cls: type[_ErrorT],
        *,
        data_class: DataClass,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        tool_name: str,
        tool_description: str,
        input_schema: dict[str, Any],
        strict: bool = True,
        model_overrides: dict[str, str] | None = None,
        session: Session | None = None,
        tenant_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        route = self._route_for(task)
        settings = get_settings()
        last_exc: Exception | None = None

        for provider_name in _dedupe(route.primary, route.fallback):
            provider = self._provider_for(provider_name)
            # The gate — checked for every candidate, unconditionally,
            # before anything else (including the KIMI_ENABLED check
            # below): a confidential call must never reach a provider
            # that isn't confidential_ok, full stop.
            ensure_data_class_allowed(provider, data_class)

            if provider_name == "kimi" and not settings.kimi_enabled:
                # Dark-launched: behave exactly as if kimi weren't
                # registered at all, try the next candidate.
                continue

            model = (model_overrides or {}).get(provider_name)
            try:
                result = provider.generate_structured(
                    error_cls,
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                    tool_name=tool_name,
                    tool_description=tool_description,
                    input_schema=input_schema,
                    strict=strict,
                )
            except error_cls as exc:
                last_exc = exc
                continue

            if session is not None:
                record_ai_call(
                    session,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    provider=provider_name,
                    model=model or provider.models[0],
                    data_class=data_class,
                    task=task,
                )
            return result

        if last_exc is not None:
            raise last_exc
        raise error_cls(
            f"No provider was available to serve task {task!r} "
            f"(KIMI_ENABLED={settings.kimi_enabled})."
        )

    def generate_text(
        self,
        task: str,
        error_cls: type[_ErrorT],
        *,
        data_class: DataClass,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        model_overrides: dict[str, str] | None = None,
        session: Session | None = None,
        tenant_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> str:
        route = self._route_for(task)
        settings = get_settings()
        last_exc: Exception | None = None

        for provider_name in _dedupe(route.primary, route.fallback):
            provider = self._provider_for(provider_name)
            ensure_data_class_allowed(provider, data_class)

            if provider_name == "kimi" and not settings.kimi_enabled:
                continue

            model = (model_overrides or {}).get(provider_name)
            try:
                result = provider.generate_text(
                    error_cls,
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                )
            except error_cls as exc:
                last_exc = exc
                continue

            if session is not None:
                record_ai_call(
                    session,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    provider=provider_name,
                    model=model or provider.models[0],
                    data_class=data_class,
                    task=task,
                )
            return result

        if last_exc is not None:
            raise last_exc
        raise error_cls(
            f"No provider was available to serve task {task!r} "
            f"(KIMI_ENABLED={settings.kimi_enabled})."
        )


@lru_cache
def get_ai_router() -> AIRouter:
    """The process-wide default router: claude + kimi, AI_ROUTING —
    constructed (and AI_ROUTING validated) the first time anything needs
    it, cached after that, same @lru_cache idiom api/config.py::get_settings
    already uses. Each of the five domain provider files calls this lazily
    at request time — see e.g. services/composition/anthropic_provider.py
    — rather than the router being constructed at process start, so a
    request that never touches AI still never needs either vendor's key
    configured."""
    return AIRouter(
        providers={"claude": ClaudeProvider(), "kimi": KimiProvider()},
        routing=AI_ROUTING,
    )

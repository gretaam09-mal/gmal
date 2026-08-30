"""AIRouter (services/ai/router.py) — the confidentiality gate itself,
config validation, dark-launch fallback, and metrics logging. The three
gate tests the spec requires are here:
  (a) test_confidential_call_routed_to_kimi_raises_before_any_network_call
  (b) test_a_public_call_to_kimi_succeeds_against_a_mocked_client
  (c) test_a_confidential_task_naming_a_non_confidential_ok_provider_fails_at_load
"""
from __future__ import annotations

from unittest.mock import Mock

import pytest
from sqlalchemy import select

from db.models import MetricsEvent, Tenant, User, Workspace
from services.ai.claude_provider import ClaudeProvider
from services.ai.errors import AIRoutingConfigError, ConfidentialRoutingError
from services.ai.kimi_provider import KimiProvider
from services.ai.router import AIRouter, get_ai_router
from services.ai.routing import AI_ROUTING, TaskRoute, validate_routing


class _DomainError(Exception):
    pass


class _FakeProvider:
    """A provider double whose generate_* methods explode if ever called —
    so a test asserting they weren't invoked is proof, not an assumption,
    and a test that *does* expect a call can inspect exactly what args it
    received."""

    def __init__(self, name: str, *, confidential_ok: bool, models=("test-model",)):
        self.name = name
        self.confidential_ok = confidential_ok
        self.models = models
        self.supports_structured = True
        self.generate_structured = Mock(
            side_effect=AssertionError(f"{name}.generate_structured should not have been called")
        )
        self.generate_text = Mock(
            side_effect=AssertionError(f"{name}.generate_text should not have been called")
        )

    def succeed_with(self, result: dict) -> None:
        self.generate_structured = Mock(return_value=result)


_CALL_KWARGS = dict(
    max_tokens=100,
    system="s",
    messages=[{"role": "user", "content": "hi"}],
    tool_name="t",
    tool_description="d",
    input_schema={"type": "object"},
)


# --- (a) the confidentiality gate ---------------------------------------


def test_confidential_call_routed_to_kimi_raises_before_any_network_call():
    """The exact scenario the spec names: a confidential call whose task
    would route to kimi. Raises ConfidentialRoutingError, and neither
    candidate provider's generate_structured is ever invoked — proof
    there is no network call, not merely an assumption."""
    kimi = _FakeProvider("kimi", confidential_ok=False)
    claude = _FakeProvider("claude", confidential_ok=True)
    router = AIRouter(
        providers={"claude": claude, "kimi": kimi},
        routing={"leaky_task": TaskRoute(primary="kimi", fallback="claude", data_class="public")},
    )

    with pytest.raises(ConfidentialRoutingError):
        router.generate_structured(
            "leaky_task", _DomainError, data_class="confidential", **_CALL_KWARGS
        )

    kimi.generate_structured.assert_not_called()
    claude.generate_structured.assert_not_called()


def test_confidential_call_routed_to_kimi_raises_even_with_kimi_enabled(monkeypatch):
    """KIMI_ENABLED must never be able to turn off the confidentiality
    gate — only whether kimi is even considered as a candidate at all."""
    import services.ai.router as router_module

    monkeypatch.setattr(router_module.get_settings(), "kimi_enabled", True, raising=False)
    kimi = _FakeProvider("kimi", confidential_ok=False)
    claude = _FakeProvider("claude", confidential_ok=True)
    router = AIRouter(
        providers={"claude": claude, "kimi": kimi},
        routing={"leaky_task": TaskRoute(primary="kimi", fallback="claude", data_class="public")},
    )

    with pytest.raises(ConfidentialRoutingError):
        router.generate_structured(
            "leaky_task", _DomainError, data_class="confidential", **_CALL_KWARGS
        )
    kimi.generate_structured.assert_not_called()


def test_the_real_production_router_also_refuses_a_confidential_extraction_call():
    """Not a toy config — the actual default AI_ROUTING/get_ai_router(),
    with the real "extraction" task (public, kimi-primary). A caller
    marking one specific extraction call confidential must still be
    refused, never silently sent to kimi."""
    router = get_ai_router()
    with pytest.raises(ConfidentialRoutingError):
        router.generate_structured(
            "extraction", _DomainError, data_class="confidential", **_CALL_KWARGS
        )


def test_a_confidential_task_never_reaches_kimi_via_generate_text_either():
    kimi = _FakeProvider("kimi", confidential_ok=False)
    claude = _FakeProvider("claude", confidential_ok=True)
    router = AIRouter(
        providers={"claude": claude, "kimi": kimi},
        routing={"leaky_task": TaskRoute(primary="kimi", fallback="claude", data_class="public")},
    )
    with pytest.raises(ConfidentialRoutingError):
        router.generate_text(
            "leaky_task",
            _DomainError,
            data_class="confidential",
            max_tokens=100,
            system="s",
            messages=[{"role": "user", "content": "hi"}],
        )
    kimi.generate_text.assert_not_called()


# --- (b) a public call to kimi succeeds ----------------------------------


def test_a_public_call_to_kimi_succeeds_against_a_mocked_client(monkeypatch):
    """The second required gate test: with KIMI_ENABLED on, a public task
    routed to kimi actually reaches it (against a mocked httpx client —
    see test_kimi_provider.py for the HTTP-level detail) and returns the
    result; claude is never touched since kimi succeeded outright."""
    import services.ai.router as router_module

    monkeypatch.setattr(router_module.get_settings(), "kimi_enabled", True, raising=False)

    kimi_http_client = Mock()
    kimi_http_client_response = {"choices": [{"message": {"content": '{"ok": true}'}}]}
    mock_httpx_response = Mock(status_code=200)
    mock_httpx_response.json.return_value = kimi_http_client_response
    kimi_http_client.post.return_value = mock_httpx_response

    kimi = KimiProvider(api_key="test-key", client=kimi_http_client)
    claude = _FakeProvider("claude", confidential_ok=True)
    router = AIRouter(
        providers={"claude": claude, "kimi": kimi},
        routing={"public_task": TaskRoute(primary="kimi", fallback="claude", data_class="public")},
    )

    result = router.generate_structured(
        "public_task", _DomainError, data_class="public", **_CALL_KWARGS
    )

    assert result == {"ok": True}
    claude.generate_structured.assert_not_called()
    kimi_http_client.post.assert_called_once()


def test_kimi_disabled_by_default_falls_back_to_claude_transparently():
    """The dark-launch guarantee: with KIMI_ENABLED at its default (off),
    a public task whose primary is kimi behaves exactly as if kimi were
    never registered — claude serves it, kimi is never touched."""
    kimi = _FakeProvider("kimi", confidential_ok=False)
    claude = _FakeProvider("claude", confidential_ok=True)
    claude.succeed_with({"ok": True})
    router = AIRouter(
        providers={"claude": claude, "kimi": kimi},
        routing={"public_task": TaskRoute(primary="kimi", fallback="claude", data_class="public")},
    )

    result = router.generate_structured(
        "public_task", _DomainError, data_class="public", **_CALL_KWARGS
    )

    assert result == {"ok": True}
    kimi.generate_structured.assert_not_called()
    claude.generate_structured.assert_called_once()


def test_kimi_failure_falls_back_to_claude(monkeypatch):
    import services.ai.router as router_module

    monkeypatch.setattr(router_module.get_settings(), "kimi_enabled", True, raising=False)
    kimi = _FakeProvider("kimi", confidential_ok=False)
    kimi.generate_structured = Mock(side_effect=_DomainError("kimi is down"))
    claude = _FakeProvider("claude", confidential_ok=True)
    claude.succeed_with({"ok": True})
    router = AIRouter(
        providers={"claude": claude, "kimi": kimi},
        routing={"public_task": TaskRoute(primary="kimi", fallback="claude", data_class="public")},
    )

    result = router.generate_structured(
        "public_task", _DomainError, data_class="public", **_CALL_KWARGS
    )

    assert result == {"ok": True}
    claude.generate_structured.assert_called_once()


def test_both_providers_failing_raises_the_last_domain_error(monkeypatch):
    import services.ai.router as router_module

    monkeypatch.setattr(router_module.get_settings(), "kimi_enabled", True, raising=False)
    kimi = _FakeProvider("kimi", confidential_ok=False)
    kimi.generate_structured = Mock(side_effect=_DomainError("kimi is down"))
    claude = _FakeProvider("claude", confidential_ok=True)
    claude.generate_structured = Mock(side_effect=_DomainError("claude is down too"))
    router = AIRouter(
        providers={"claude": claude, "kimi": kimi},
        routing={"public_task": TaskRoute(primary="kimi", fallback="claude", data_class="public")},
    )

    with pytest.raises(_DomainError, match="claude is down too"):
        router.generate_structured(
            "public_task", _DomainError, data_class="public", **_CALL_KWARGS
        )


# --- (c) invalid routing config fails at load ----------------------------


def test_a_confidential_task_naming_a_non_confidential_ok_provider_fails_at_load():
    kimi = _FakeProvider("kimi", confidential_ok=False)
    claude = _FakeProvider("claude", confidential_ok=True)

    with pytest.raises(AIRoutingConfigError, match="confidential_ok=False"):
        AIRouter(
            providers={"claude": claude, "kimi": kimi},
            routing={
                "bad_task": TaskRoute(primary="kimi", fallback="claude", data_class="confidential")
            },
        )


def test_a_confidential_task_naming_a_bad_fallback_also_fails_at_load():
    kimi = _FakeProvider("kimi", confidential_ok=False)
    claude = _FakeProvider("claude", confidential_ok=True)

    with pytest.raises(AIRoutingConfigError, match="confidential_ok=False"):
        AIRouter(
            providers={"claude": claude, "kimi": kimi},
            routing={
                "bad_task": TaskRoute(primary="claude", fallback="kimi", data_class="confidential")
            },
        )


def test_a_task_naming_an_unregistered_provider_fails_at_load():
    claude = _FakeProvider("claude", confidential_ok=True)

    with pytest.raises(AIRoutingConfigError, match="unregistered provider"):
        AIRouter(
            providers={"claude": claude},
            routing={
                "bad_task": TaskRoute(primary="ghost", fallback="claude", data_class="public")
            },
        )


def test_calling_an_unregistered_task_raises_a_routing_config_error():
    claude = _FakeProvider("claude", confidential_ok=True)
    router = AIRouter(providers={"claude": claude}, routing={})

    with pytest.raises(AIRoutingConfigError, match="No AI_ROUTING entry"):
        router.generate_structured(
            "never_registered", _DomainError, data_class="public", **_CALL_KWARGS
        )


def test_the_real_production_ai_routing_is_itself_valid():
    """A regression guard on AI_ROUTING (services/ai/routing.py) directly
    — validate_routing is exactly what AIRouter.__init__ runs at
    construction, so this proves the real config is internally
    consistent independent of whatever this file's other tests exercise
    with toy configs."""
    validate_routing({"claude": ClaudeProvider(), "kimi": KimiProvider()}, AI_ROUTING)


# --- metrics logging -------------------------------------------------------


def test_a_successful_call_logs_provider_model_data_class_and_task(db_session):
    user = User(clerk_user_id="clerk_ai_metrics", email="ai-metrics@example.com")
    db_session.add(user)
    db_session.flush()
    tenant = Tenant(name="Fund A", slug="fund-ai-metrics", created_by_user_id=user.id)
    db_session.add(tenant)
    db_session.flush()
    workspace = Workspace(
        tenant_id=tenant.id, codename="project-falcon", created_by_user_id=user.id
    )
    db_session.add(workspace)
    db_session.flush()
    tenant_id, workspace_id = tenant.id, workspace.id

    claude = _FakeProvider("claude", confidential_ok=True, models=("claude-sonnet-5",))
    claude.succeed_with({"ok": True})
    router = AIRouter(
        providers={"claude": claude},
        routing={
            "memo_composition": TaskRoute(
                primary="claude", fallback="claude", data_class="confidential"
            )
        },
    )

    router.generate_structured(
        "memo_composition",
        _DomainError,
        data_class="confidential",
        session=db_session,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        **_CALL_KWARGS,
    )

    event = db_session.execute(
        select(MetricsEvent).where(MetricsEvent.event_name == "ai.call")
    ).scalar_one()
    assert event.tenant_id == tenant_id
    assert event.workspace_id == workspace_id
    assert event.properties == {
        "provider": "claude",
        "model": "claude-sonnet-5",
        "data_class": "confidential",
        "task": "memo_composition",
    }


def test_no_metrics_event_is_written_when_no_session_is_given():
    """Metrics logging is instrumentation, not enforcement — a caller with
    no session in scope (there is none today; this proves the contract)
    still gets its result, it just isn't logged."""
    claude = _FakeProvider("claude", confidential_ok=True)
    claude.succeed_with({"ok": True})
    router = AIRouter(
        providers={"claude": claude},
        routing={
            "memo_composition": TaskRoute(
                primary="claude", fallback="claude", data_class="confidential"
            )
        },
    )

    result = router.generate_structured(
        "memo_composition", _DomainError, data_class="confidential", **_CALL_KWARGS
    )
    assert result == {"ok": True}

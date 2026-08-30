"""Logs every AI call the router actually makes to metrics_events —
provider, model, data_class, and task — per
docs/Provision_Kimi_Integration_Spec.md section 6. Same pattern
services/metrics.py already uses for board metrics: one MetricsEvent row
per occurrence, written from the code that actually did the thing, not
recomputed later.

tenant_id/workspace_id are threaded through from whichever caller has
them in scope (see services/ai/router.py::AIRouter.generate_structured)
and are None for tasks that aren't about one tenant's data — extraction
and rule-drafting run over shared reference-data instruments, not a
workspace's own content (see services/instrument_onboarding.py's module
docstring) — same nullable-for-platform-level-events design
MetricsEvent and AuditEvent already use elsewhere in this codebase.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from db.models import MetricsEvent
from services.ai.providers import DataClass

AI_CALL_EVENT = "ai.call"


def record_ai_call(
    session: Session,
    *,
    tenant_id: uuid.UUID | None,
    workspace_id: uuid.UUID | None,
    provider: str,
    model: str,
    data_class: DataClass,
    task: str,
) -> MetricsEvent:
    event = MetricsEvent(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        event_name=AI_CALL_EVENT,
        properties={
            "provider": provider,
            "model": model,
            "data_class": data_class,
            "task": task,
        },
    )
    session.add(event)
    session.flush()
    return event

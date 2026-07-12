"""F5 orchestration: recording and reading scenario probabilities for
in-flight instruments — the DB-touching half of engine/impact/scenarios.py.

Every probability an expert sets is timestamped into the append-only
forecast_log (never overwritten or deleted — a correction is a new
entry); an analysis run reads only the latest entry per scenario. No
forecasting UI beyond this — the probabilities surface in memo prose via
the assumption register, not as a standalone screen.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ForecastLogEntry

FORECAST_TYPE = "scenario_probability"


class ScenarioInput(NamedTuple):
    scenario: str
    probability: Decimal
    magnitude_multiplier: Decimal
    source: str


class ScenarioRecord(NamedTuple):
    scenario: str
    probability: Decimal
    magnitude_multiplier: Decimal
    source: str
    recorded_at: str


def record_scenario_probabilities(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    predicate_id: uuid.UUID,
    inputs: list[ScenarioInput],
) -> list[ForecastLogEntry]:
    """Writes one forecast_log entry per scenario, all sharing this call's
    timestamp — see CreatedAtMixin. Probabilities need not sum to exactly
    1 here (engine/impact/scenarios.compute_weighted_range normalises),
    but callers should pass a documented base-rate split or an expert's
    considered override, not arbitrary numbers."""
    entries = []
    for record in inputs:
        entry = ForecastLogEntry(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            predicate_id=predicate_id,
            forecast_type=FORECAST_TYPE,
            payload={
                "scenario": record.scenario,
                "probability": str(record.probability),
                "magnitude_multiplier": str(record.magnitude_multiplier),
                "source": record.source,
            },
        )
        session.add(entry)
        entries.append(entry)
    session.flush()
    return entries


def get_latest_scenario_weights(
    session: Session, predicate_id: uuid.UUID
) -> dict[str, ScenarioRecord]:
    """The most recent forecast_log entry per distinct scenario name for
    this predicate — empty if no expert has recorded probabilities yet,
    in which case callers fall back to engine/impact/scenarios.BASE_RATE_TABLES."""
    rows = session.execute(
        select(ForecastLogEntry)
        .where(
            ForecastLogEntry.predicate_id == predicate_id,
            ForecastLogEntry.forecast_type == FORECAST_TYPE,
        )
        .order_by(ForecastLogEntry.created_at.desc())
    ).scalars()
    latest: dict[str, ScenarioRecord] = {}
    for row in rows:
        scenario = row.payload["scenario"]
        if scenario in latest:
            continue
        latest[scenario] = ScenarioRecord(
            scenario=scenario,
            probability=Decimal(row.payload["probability"]),
            magnitude_multiplier=Decimal(row.payload.get("magnitude_multiplier", "1")),
            source=row.payload.get("source", "unknown"),
            recorded_at=row.created_at.isoformat(),
        )
    return latest

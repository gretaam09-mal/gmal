"""F9: the daily source sweep. Hashes each curated source's current
content, diffs it against what was last seen, and for any source mapped
to an instrument, records a new InstrumentVersion and flags every
APPROVED memo (in every tenant) that used the superseded version.

Curated sources and instruments are platform-wide reference data (see
db/models/ops.py::CuratedSource, db/models/regulatory.py), so most of
this runs on one unscoped session; flagging memos needs tenant-scoped
reads/writes, done by switching that same connection's RLS context
tenant-by-tenant (set_rls_context is SET, not SET LOCAL, precisely so a
long-running job like this can do that — see db/session.py).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    Clause,
    CuratedSource,
    Instrument,
    InstrumentVersion,
    Memo,
    MemoInputChangeFlag,
    MemoVersion,
    Obligation,
    Predicate,
    SweepRun,
    Tenant,
)
from db.models.enums import MemoStatus, SweepRunStatus
from db.session import set_rls_context
from services.ingestion import hash_text
from services.instrument_onboarding import ingest_new_instrument_version
from services.sources.fetcher import SourceFetcher


@dataclass(frozen=True)
class FlaggedMemo:
    tenant_id: uuid.UUID
    workspace_id: uuid.UUID
    memo_id: uuid.UUID
    memo_title: str
    memo_version_id: uuid.UUID


@dataclass(frozen=True)
class SweepChange:
    curated_source_key: str
    instrument_title: str
    instrument_id: uuid.UUID
    old_instrument_version_id: uuid.UUID
    new_instrument_version_id: uuid.UUID
    flagged_memos: list[FlaggedMemo] = field(default_factory=list)


def _predicate_ids(content: dict) -> list[uuid.UUID]:
    ids = [o["predicate_id"] for o in content.get("obligations", [])]
    ids += [e["predicate_id"] for e in content.get("excluded", [])]
    return [uuid.UUID(pid) for pid in ids]


def _flag_memos_using_instrument_version(
    session: Session,
    *,
    old_instrument_version: InstrumentVersion,
    new_version: InstrumentVersion,
    instrument: Instrument,
) -> list[FlaggedMemo]:
    flagged: list[FlaggedMemo] = []
    tenants = session.execute(select(Tenant)).scalars().all()
    for tenant in tenants:
        set_rls_context(session, tenant.id, None)
        rows = session.execute(
            select(MemoVersion, Memo)
            .join(Memo, Memo.id == MemoVersion.memo_id)
            .where(MemoVersion.status == MemoStatus.APPROVED)
        ).all()
        for version, memo in rows:
            predicate_ids = _predicate_ids(version.content)
            if not predicate_ids:
                continue
            uses_old_version = session.execute(
                select(Predicate.id)
                .join(Obligation, Obligation.id == Predicate.obligation_id)
                .join(Clause, Clause.id == Obligation.clause_id)
                .where(
                    Predicate.id.in_(predicate_ids),
                    Clause.instrument_version_id == old_instrument_version.id,
                )
            ).first()
            if uses_old_version is None:
                continue
            session.add(
                MemoInputChangeFlag(
                    tenant_id=version.tenant_id,
                    workspace_id=version.workspace_id,
                    memo_version_id=version.id,
                    instrument_id=instrument.id,
                    instrument_version_id=old_instrument_version.id,
                    description=(
                        f"{instrument.title} was updated to version "
                        f"{new_version.version_label}; this memo used the superseded version."
                    ),
                )
            )
            flagged.append(
                FlaggedMemo(
                    tenant_id=tenant.id,
                    workspace_id=version.workspace_id,
                    memo_id=memo.id,
                    memo_title=memo.title,
                    memo_version_id=version.id,
                )
            )
        session.flush()
    return flagged


def run_sweep(session: Session, fetcher: SourceFetcher) -> tuple[SweepRun, list[SweepChange]]:
    now = datetime.now(UTC)
    sweep_run = SweepRun(
        run_type="daily_source_sweep", status=SweepRunStatus.RUNNING, started_at=now
    )
    session.add(sweep_run)
    session.flush()

    changes: list[SweepChange] = []
    errors: list[str] = []
    sources = list(session.execute(select(CuratedSource)).scalars())
    for source in sources:
        try:
            content = fetcher.fetch(source.url)
        except Exception as exc:
            # One source's fetch failure must not abort the whole sweep.
            errors.append(f"{source.key}: {exc}")
            continue
        new_hash = hash_text(content)
        changed = new_hash != source.last_content_hash
        source.last_content_hash = new_hash
        source.last_swept_at = now
        if not changed or source.instrument_id is None:
            continue

        instrument = session.get(Instrument, source.instrument_id)
        old_version = session.execute(
            select(InstrumentVersion).where(
                InstrumentVersion.instrument_id == instrument.id,
                InstrumentVersion.valid_to.is_(None),
            )
        ).scalar_one()
        if old_version.content_hash == new_hash:
            continue  # already up to date, e.g. a source just mapped to an instrument

        new_version = ingest_new_instrument_version(
            session,
            instrument=instrument,
            version_label=f"sweep-{now.date().isoformat()}",
            source_url=source.url,
            raw_text=content,
        )
        flagged = _flag_memos_using_instrument_version(
            session,
            old_instrument_version=old_version,
            new_version=new_version,
            instrument=instrument,
        )
        changes.append(
            SweepChange(
                curated_source_key=source.key,
                instrument_title=instrument.title,
                instrument_id=instrument.id,
                old_instrument_version_id=old_version.id,
                new_instrument_version_id=new_version.id,
                flagged_memos=flagged,
            )
        )

    sweep_run.status = SweepRunStatus.COMPLETE
    sweep_run.completed_at = datetime.now(UTC)
    sweep_run.summary = {
        "sources_checked": len(sources),
        "changed_sources": [c.curated_source_key for c in changes],
        "memos_flagged": sum(len(c.flagged_memos) for c in changes),
        "errors": errors,
    }
    session.flush()
    return sweep_run, changes

"""F9: the daily source sweep, registered as a Procrastinate periodic
task. Runs services.sources.sweep.run_sweep against the curated sources,
then emails every affected workspace via services.sources.notify.
"""
from __future__ import annotations

from db.session import raw_session
from jobs.app import app
from services.notifications.email import StubEmailProvider
from services.sources.fetcher import FixtureSourceFetcher
from services.sources.notify import notify_affected_memos
from services.sources.sweep import run_sweep


def _default_fetcher() -> FixtureSourceFetcher:
    """F9's confirmed scope: no live HTTP fetch against the FCA Handbook /
    PRA Rulebook / legislation.gov.uk / UK Parliament API. A real fetcher
    can replace this without touching run_sweep, which only depends on
    the SourceFetcher protocol."""
    return FixtureSourceFetcher()


@app.periodic(cron="0 6 * * *")
@app.task(queue="sources")
def daily_source_sweep(timestamp: int) -> dict:
    with raw_session() as session:
        sweep_run, changes = run_sweep(session, _default_fetcher())
        notify_affected_memos(session, StubEmailProvider(), changes)
        session.commit()
        return sweep_run.summary

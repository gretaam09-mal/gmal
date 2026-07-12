import jobs  # noqa: F401 -- registers jobs.sources' @app.task/@app.periodic tasks
from jobs.sources import daily_source_sweep


def test_daily_source_sweep_task_runs_and_returns_a_summary(db_session):
    """A wiring smoke test for the Procrastinate task itself — the sweep
    mechanics (hash diff, instrument versioning, memo flagging) are
    covered by tests/integration/test_source_sweep.py directly against
    services.sources.sweep.run_sweep."""
    summary = daily_source_sweep.func(0)

    assert set(summary.keys()) == {"sources_checked", "changed_sources", "memos_flagged", "errors"}

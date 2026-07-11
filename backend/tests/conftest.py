import os
import subprocess
import sys
from pathlib import Path

# Point the app at a dedicated test database *before* anything imports
# api.config, so the process-wide cached Settings picks it up.
os.environ.setdefault(
    "PROVISION_DATABASE_URL",
    "postgresql+psycopg://provision:provision@localhost:5432/provision_test",
)

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from db.base import Base  # noqa: E402
from db.models import *  # noqa: E402,F401,F403 -- registers all tables
from db.session import get_engine, raw_session  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def _migrated_test_database():
    """Apply real Alembic migrations to the test database once per run.

    Using the real migrations (not Base.metadata.create_all) means the
    immutability triggers are actually under test, not just the tables.
    """
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
        env={**os.environ},
    )
    yield


@pytest.fixture
def db_session() -> Session:
    """A session bound to one connection for the whole test, truncated
    clean afterwards.

    One connection (not a connectionless pooled Session) so set_rls_context
    survives an intermediate commit within a test — see the note on
    set_rls_context in db/session.py. TRUNCATE doesn't fire the row-level
    immutability triggers (they're FOR EACH ROW, TRUNCATE only fires
    statement-level triggers), so this works even on append-only tables.
    """
    with raw_session() as session:
        try:
            yield session
        finally:
            session.rollback()
            table_names = [t.name for t in Base.metadata.sorted_tables]
            with get_engine().begin() as conn:
                conn.execute(text(f"TRUNCATE {', '.join(table_names)} RESTART IDENTITY CASCADE"))

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from api.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def tenant_session(tenant_id: str) -> Iterator[Session]:
    """Yield a Session scoped to a single tenant.

    CONVENTIONS.md rule #3: no database query without tenant scoping.
    Sets a Postgres session variable (app.tenant_id) that row-level
    security policies key off, so scoping is enforced at the database
    layer rather than trusted to every call site.
    """
    session = get_sessionmaker()()
    try:
        session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, false)"),
            {"tenant_id": tenant_id},
        )
        yield session
    finally:
        session.close()

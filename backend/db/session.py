import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.orm import Session

from api.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def get_sessionmaker():
    """Deprecated alias kept for call sites that don't need RLS context —
    prefer workspace_session/tenant_session, which bind to one connection
    for the request so Postgres session variables survive intermediate
    commits. See the note in workspace_session for why that matters."""
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def set_rls_context(
    conn_or_session: Connection | Session,
    tenant_id: str | uuid.UUID,
    workspace_id: str | uuid.UUID | None = None,
) -> None:
    """Set app.tenant_id / app.workspace_id for the rest of this connection.

    Uses is_local=false (SET, not SET LOCAL) deliberately: a request may
    span several commits (e.g. create a workspace, narrow scope, then
    insert its first membership), and SET LOCAL is cleared at the end of
    each transaction. This is safe only because callers of this module
    bind one Connection per request/context (see workspace_session and
    api/deps.py) — a pooled, connectionless Session would leak this
    setting to whatever the next checkout does with that connection.
    """
    conn_or_session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, false)"),
        {"tenant_id": str(tenant_id)},
    )
    conn_or_session.execute(
        text("SELECT set_config('app.workspace_id', :workspace_id, false)"),
        {"workspace_id": str(workspace_id) if workspace_id is not None else ""},
    )


def set_user_context(conn_or_session: Connection | Session, user_id: str | uuid.UUID) -> None:
    """Set app.user_id for the rest of this connection.

    Lets a session that doesn't yet know a tenant/workspace (because it's
    about to discover one, e.g. "which workspace is /workspaces/{id} in
    and am I a member") read its own membership rows via the
    memberships_self_read policy, without that policy widening what any
    *other* row is visible to. See the row_level_security migration.
    """
    conn_or_session.execute(
        text("SELECT set_config('app.user_id', :user_id, false)"),
        {"user_id": str(user_id)},
    )


@contextmanager
def raw_session() -> Iterator[Session]:
    """A Session bound to one dedicated connection for its whole lifetime.

    Used even for "unscoped" work (identity lookups) so that a handler
    can freely mix raw and RLS-scoped queries via set_rls_context/
    set_user_context on the *same* connection without losing that context
    to connection-pool churn across commits.
    """
    connection = get_engine().connect()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        connection.close()


@contextmanager
def workspace_session(
    tenant_id: str | uuid.UUID, workspace_id: str | uuid.UUID | None = None
) -> Iterator[Session]:
    """Yield a Session scoped to a tenant and, usually, a single workspace.

    CONVENTIONS.md rule #3: no database query without tenant scoping.
    Sets Postgres session variables (app.tenant_id, app.workspace_id) that
    the row-level security policies in the row_level_security migration
    key off, so scoping is enforced at the database layer rather than
    trusted to every call site. Leave workspace_id unset only for
    genuinely tenant-wide reads (e.g. "list my workspaces") — every
    request handling one specific workspace must pass it, which is what
    keeps two workspaces in the same tenant isolated from each other.
    """
    with raw_session() as session:
        set_rls_context(session, tenant_id, workspace_id)
        yield session


@contextmanager
def tenant_session(tenant_id: str | uuid.UUID) -> Iterator[Session]:
    """Tenant-wide session with no workspace filter. See workspace_session."""
    with workspace_session(tenant_id, None) as session:
        yield session

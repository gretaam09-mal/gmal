"""row level security

Revision ID: ebff3e065651
Revises: 6741d4c91229
Create Date: 2026-07-10 23:34:34.051559

"""
from collections.abc import Sequence

from alembic import op

revision: str = 'ebff3e065651'
down_revision: str | None = '6741d4c91229'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# CONVENTIONS.md rule #3: no database query without tenant scoping. This is
# the DB-layer backstop: application code sets app.tenant_id (always) and
# app.workspace_id (whenever a request is scoped to one workspace) via
# db/session.py::workspace_session, and these policies enforce it even if
# a query forgets a WHERE clause. FORCE ROW LEVEL SECURITY matters here:
# without it, the table owner (the app's own DB role) would bypass RLS.
#
# app.workspace_id == '' means "no workspace filter" (tenant-wide reads,
# e.g. listing a tenant's workspaces) — anything but '' restricts strictly
# to that one workspace, which is what makes two workspaces in the same
# tenant fully isolated from each other, not just from other tenants.

# tenant_id only — the row itself represents (or predates) a workspace.
_TENANT_ONLY_TABLES = ("workspaces",)

# tenant_id + required workspace_id.
_WORKSPACE_SCOPED_TABLES = (
    "memberships",
    "entity_profiles",
    "profile_fields",
    "analyses",
    "analysis_items",
    "memos",
    "memo_versions",
    "assumptions",
    "reviews",
    "forecast_log",
    "source_documents",
    "reports",
)

# tenant_id + nullable workspace_id (some rows are tenant-level).
_TENANT_WITH_OPTIONAL_WORKSPACE_TABLES = ("audit_events", "sweep_runs")

_TENANT_ONLY_USING = (
    "tenant_id::text = current_setting('app.tenant_id', true)"
)
_WORKSPACE_SCOPED_USING = (
    "tenant_id::text = current_setting('app.tenant_id', true) "
    "AND (current_setting('app.workspace_id', true) = '' "
    "OR workspace_id::text = current_setting('app.workspace_id', true))"
)


def _enable(table: str, using: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY {table}_tenant_isolation ON {table} USING ({using})")


def _disable(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    for table in _TENANT_ONLY_TABLES:
        _enable(table, _TENANT_ONLY_USING)
    for table in _WORKSPACE_SCOPED_TABLES:
        _enable(table, _WORKSPACE_SCOPED_USING)
    for table in _TENANT_WITH_OPTIONAL_WORKSPACE_TABLES:
        _enable(table, _WORKSPACE_SCOPED_USING)


def downgrade() -> None:
    for table in (
        _TENANT_ONLY_TABLES + _WORKSPACE_SCOPED_TABLES + _TENANT_WITH_OPTIONAL_WORKSPACE_TABLES
    ):
        _disable(table)

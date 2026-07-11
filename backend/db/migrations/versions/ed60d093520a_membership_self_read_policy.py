"""membership self read policy

Revision ID: ed60d093520a
Revises: 2b7f48ee11c9
Create Date: 2026-07-10 23:50:54.245168

"""
from collections.abc import Sequence

from alembic import op

revision: str = 'ed60d093520a'
down_revision: str | None = '2b7f48ee11c9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Bootstrap fix for the memberships_tenant_isolation policy (see
# row_level_security migration): a request that only knows a workspace_id
# (e.g. GET /workspaces/{id}) can't set app.tenant_id until it has read
# the membership row that *tells it* the tenant_id — but that policy
# requires app.tenant_id to already be set. This adds a second, PERMISSIVE
# SELECT-only policy: a session that has set app.user_id (and nothing
# else) can read its own membership rows, and only its own. Postgres ORs
# multiple permissive policies together for the same command, so a row is
# visible if EITHER policy's condition holds; mutations still require the
# original tenant+workspace policy since this one is SELECT-only.
_POLICY = "memberships_self_read"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE POLICY {_POLICY} ON memberships
        FOR SELECT
        USING (user_id::text = current_setting('app.user_id', true))
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {_POLICY} ON memberships")

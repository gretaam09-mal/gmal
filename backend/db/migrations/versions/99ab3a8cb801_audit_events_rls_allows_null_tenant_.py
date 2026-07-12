"""audit events rls allows null tenant platform events

Revision ID: 99ab3a8cb801
Revises: 922734da6fa6
Create Date: 2026-07-12 19:53:19.613624

"""
from collections.abc import Sequence

from alembic import op

revision: str = "99ab3a8cb801"
down_revision: str | None = "922734da6fa6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_USING = (
    "tenant_id::text = current_setting('app.tenant_id', true) "
    "AND (current_setting('app.workspace_id', true) = '' "
    "OR workspace_id::text = current_setting('app.workspace_id', true))"
)
_NEW_USING = f"tenant_id IS NULL OR ({_OLD_USING})"


def upgrade() -> None:
    # A NULL tenant_id row (F10: a user's first sign-in, before they've
    # joined or created a tenant) has no tenant to isolate — allow it
    # through both the write side (so the INSERT itself isn't rejected)
    # and the read side. This can't leak into any tenant's audit log view:
    # every read path also filters by workspace_id in application code
    # (see GET /workspaces/{id}/audit-events), and a first-sign-in row's
    # workspace_id is always NULL too.
    op.execute("DROP POLICY IF EXISTS audit_events_tenant_isolation ON audit_events")
    op.execute(f"CREATE POLICY audit_events_tenant_isolation ON audit_events USING ({_NEW_USING})")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_events_tenant_isolation ON audit_events")
    op.execute(f"CREATE POLICY audit_events_tenant_isolation ON audit_events USING ({_OLD_USING})")

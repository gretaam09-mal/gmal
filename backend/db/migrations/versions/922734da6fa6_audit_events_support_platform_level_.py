"""audit events support platform level rows for first sign in

Revision ID: 922734da6fa6
Revises: f98f10d39ed5
Create Date: 2026-07-12 19:52:07.745988

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "922734da6fa6"
down_revision: str | None = "f98f10d39ed5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A handful of events predate any tenant (F10: a user's first sign-in,
    # before they've joined or created one) — audit_events_tenant_isolation
    # (row_level_security migration) already hides NULL-tenant rows from
    # every tenant-scoped session, so no RLS policy change is needed here.
    op.alter_column("audit_events", "tenant_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("audit_events", "tenant_id", existing_type=sa.UUID(), nullable=False)

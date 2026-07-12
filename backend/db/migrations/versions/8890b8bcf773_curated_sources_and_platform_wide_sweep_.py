"""curated sources and platform-wide sweep runs

Revision ID: 8890b8bcf773
Revises: a1f5c2d9e8b3
Create Date: 2026-07-12 19:37:09.833820

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8890b8bcf773"
down_revision: str | None = "a1f5c2d9e8b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "curated_sources",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("instrument_id", sa.UUID(), nullable=True),
        sa.Column("last_content_hash", sa.String(), nullable=True),
        sa.Column("last_swept_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_curated_sources_instrument_id_instruments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_curated_sources")),
        sa.UniqueConstraint("key", name=op.f("uq_curated_sources_key")),
    )

    # sweep_runs stops being tenant data and becomes platform-wide, like
    # metrics_events/error_register — a sweep checks sources shared by
    # every tenant, not one tenant's rows. Drop its RLS policy and the
    # NOT NULL on tenant_id to match.
    op.execute("DROP POLICY IF EXISTS sweep_runs_tenant_isolation ON sweep_runs")
    op.execute("ALTER TABLE sweep_runs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sweep_runs DISABLE ROW LEVEL SECURITY")

    op.add_column(
        "sweep_runs",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.alter_column("sweep_runs", "tenant_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("sweep_runs", "tenant_id", existing_type=sa.UUID(), nullable=False)
    op.drop_column("sweep_runs", "created_at")

    op.execute("ALTER TABLE sweep_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sweep_runs FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY sweep_runs_tenant_isolation ON sweep_runs USING ("
        "tenant_id::text = current_setting('app.tenant_id', true) "
        "AND (current_setting('app.workspace_id', true) = '' "
        "OR workspace_id::text = current_setting('app.workspace_id', true)))"
    )

    op.drop_table("curated_sources")

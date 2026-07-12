"""review_corrections and memo_input_change_flags immutability triggers

Revision ID: a1f5c2d9e8b3
Revises: 688c6b4d633a
Create Date: 2026-07-12 15:20:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = 'a1f5c2d9e8b3'
down_revision: str | None = '688c6b4d633a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Both new F7/F9 tables are pure event logs — a correction or a staleness
# signal is recorded once and never edited or retracted, same shape as
# audit_events/forecast_log (6741d4c91229). Reuses that migration's
# reject_update_delete() function rather than defining a new one.
_APPEND_ONLY_TABLES = ("review_corrections", "memo_input_change_flags")

_REJECT_FUNCTION = "reject_update_delete"


def _exec(sql: str) -> None:
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
    for table in _APPEND_ONLY_TABLES:
        _exec(
            f"""
            CREATE TRIGGER {table}_reject_update_delete
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION {_REJECT_FUNCTION}();
            """
        )


def downgrade() -> None:
    for table in _APPEND_ONLY_TABLES:
        _exec(f"DROP TRIGGER IF EXISTS {table}_reject_update_delete ON {table};")

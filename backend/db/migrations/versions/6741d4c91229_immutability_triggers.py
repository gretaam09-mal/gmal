"""immutability triggers

Revision ID: 6741d4c91229
Revises: 286f163a5509
Create Date: 2026-07-10 23:30:32.349017

"""
from collections.abc import Sequence

from alembic import op

revision: str = '6741d4c91229'
down_revision: str | None = '286f163a5509'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# CONVENTIONS.md rule #2: approved records are immutable. Application code
# never issues UPDATE/DELETE against these tables, but a DB trigger is the
# backstop that makes that a guarantee rather than a convention.
_STRICTLY_APPEND_ONLY_TABLES = ("audit_events", "memo_versions", "forecast_log", "profile_fields")

_REJECT_FUNCTION = "reject_update_delete"
_ENTITY_PROFILE_FUNCTION = "reject_entity_profile_mutation"


def _exec(sql: str) -> None:
    # exec_driver_sql sends the string to the DBAPI as-is, with no bind
    # parameter / paramstyle processing — required here because these
    # plpgsql bodies contain literal '%' RAISE placeholders that
    # op.execute()'s text()-based path can mangle.
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
    _exec(
        f"""
        CREATE FUNCTION {_REJECT_FUNCTION}() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                '%% rows are append-only and cannot be modified by %% (see docs/CONVENTIONS.md rule 2)',
                TG_TABLE_NAME, TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in _STRICTLY_APPEND_ONLY_TABLES:
        _exec(
            f"""
            CREATE TRIGGER {table}_reject_update_delete
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION {_REJECT_FUNCTION}();
            """
        )

    # entity_profiles is versioned-immutable with one narrow exception:
    # flipping is_current when a newer version is inserted. Everything
    # else about a version, and DELETE entirely, is rejected.
    _exec(
        f"""
        CREATE FUNCTION {_ENTITY_PROFILE_FUNCTION}() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION
                    'entity_profiles rows are immutable and cannot be deleted (see docs/CONVENTIONS.md rule 2)';
            END IF;
            IF TG_OP = 'UPDATE' AND (
                NEW.id IS DISTINCT FROM OLD.id OR
                NEW.tenant_id IS DISTINCT FROM OLD.tenant_id OR
                NEW.workspace_id IS DISTINCT FROM OLD.workspace_id OR
                NEW.version IS DISTINCT FROM OLD.version OR
                NEW.companies_house_number IS DISTINCT FROM OLD.companies_house_number OR
                NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id OR
                NEW.valid_from IS DISTINCT FROM OLD.valid_from OR
                NEW.valid_to IS DISTINCT FROM OLD.valid_to OR
                NEW.recorded_at IS DISTINCT FROM OLD.recorded_at
            ) THEN
                RAISE EXCEPTION
                    'entity_profiles rows are immutable except is_current (see docs/CONVENTIONS.md rule 2)';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    _exec(
        f"""
        CREATE TRIGGER entity_profiles_reject_mutation
        BEFORE UPDATE OR DELETE ON entity_profiles
        FOR EACH ROW EXECUTE FUNCTION {_ENTITY_PROFILE_FUNCTION}();
        """
    )


def downgrade() -> None:
    _exec("DROP TRIGGER IF EXISTS entity_profiles_reject_mutation ON entity_profiles;")
    _exec(f"DROP FUNCTION IF EXISTS {_ENTITY_PROFILE_FUNCTION}();")
    for table in _STRICTLY_APPEND_ONLY_TABLES:
        _exec(f"DROP TRIGGER IF EXISTS {table}_reject_update_delete ON {table};")
    _exec(f"DROP FUNCTION IF EXISTS {_REJECT_FUNCTION}();")

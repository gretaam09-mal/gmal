"""memo immutability triggers

Revision ID: a3f1c9d47b2e
Revises: f482eaa41929
Create Date: 2026-07-12 14:20:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = 'a3f1c9d47b2e'
down_revision: str | None = 'f482eaa41929'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# memo_versions was put in the blanket append-only list in 6741d4c91229,
# but F6's Draft -> In Review workflow needs to edit content/status in
# place before approval (override -> recompute, without minting a new
# version each time). This replaces that blanket trigger with the narrow
# "locked only once APPROVED" pattern already used for predicates
# (8773e87dd92a) — CONVENTIONS.md rule #2 still holds, just scoped to
# post-approval. reviews becomes append-only (reuses reject_update_delete()
# from 6741d4c91229 — a review decision, once recorded, is never edited).
# assumptions is locked transitively: once its parent memo_version is
# APPROVED, its assumption rows are frozen too, including new inserts —
# a change to an approved memo's assumptions must create a new
# MemoVersion (see services/memo.py once it exists), not touch the old
# one's children.

_MEMO_VERSION_FUNCTION = "reject_memo_version_mutation_after_approval"
_ASSUMPTION_FUNCTION = "reject_assumption_mutation_after_parent_approval"
_REJECT_FUNCTION = "reject_update_delete"


def _exec(sql: str) -> None:
    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
    _exec("DROP TRIGGER IF EXISTS memo_versions_reject_update_delete ON memo_versions;")

    _exec(
        f"""
        CREATE FUNCTION {_MEMO_VERSION_FUNCTION}() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.status = 'APPROVED' THEN
                    RAISE EXCEPTION
                        'approved memo versions cannot be deleted (see docs/CONVENTIONS.md rule 2)';
                END IF;
                RETURN OLD;
            END IF;
            IF OLD.status = 'APPROVED' THEN
                RAISE EXCEPTION
                    'approved memo versions are immutable — create a new version instead (see docs/CONVENTIONS.md rule 2)';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    _exec(
        f"""
        CREATE TRIGGER memo_versions_reject_mutation_after_approval
        BEFORE UPDATE OR DELETE ON memo_versions
        FOR EACH ROW EXECUTE FUNCTION {_MEMO_VERSION_FUNCTION}();
        """
    )

    _exec(
        """
        CREATE TRIGGER reviews_reject_update_delete
        BEFORE UPDATE OR DELETE ON reviews
        FOR EACH ROW EXECUTE FUNCTION reject_update_delete();
        """
    )

    _exec(
        f"""
        CREATE FUNCTION {_ASSUMPTION_FUNCTION}() RETURNS trigger AS $$
        DECLARE
            target_row assumptions%%ROWTYPE;
            parent_status memo_status;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                target_row := OLD;
            ELSE
                target_row := NEW;
            END IF;
            SELECT status INTO parent_status FROM memo_versions WHERE id = target_row.memo_version_id;
            IF parent_status = 'APPROVED' THEN
                RAISE EXCEPTION
                    'assumptions on an approved memo version are immutable — create a new memo version instead (see docs/CONVENTIONS.md rule 2)';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    _exec(
        f"""
        CREATE TRIGGER assumptions_reject_mutation_after_parent_approval
        BEFORE INSERT OR UPDATE OR DELETE ON assumptions
        FOR EACH ROW EXECUTE FUNCTION {_ASSUMPTION_FUNCTION}();
        """
    )


def downgrade() -> None:
    _exec("DROP TRIGGER IF EXISTS assumptions_reject_mutation_after_parent_approval ON assumptions;")
    _exec(f"DROP FUNCTION IF EXISTS {_ASSUMPTION_FUNCTION}();")
    _exec("DROP TRIGGER IF EXISTS reviews_reject_update_delete ON reviews;")
    _exec("DROP TRIGGER IF EXISTS memo_versions_reject_mutation_after_approval ON memo_versions;")
    _exec(f"DROP FUNCTION IF EXISTS {_MEMO_VERSION_FUNCTION}();")
    _exec(
        """
        CREATE TRIGGER memo_versions_reject_update_delete
        BEFORE UPDATE OR DELETE ON memo_versions
        FOR EACH ROW EXECUTE FUNCTION reject_update_delete();
        """
    )

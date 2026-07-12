"""instrument onboarding immutability triggers

Revision ID: 8773e87dd92a
Revises: b8fc7df2da0c
Create Date: 2026-07-11 20:20:29.010258

"""
from collections.abc import Sequence

from alembic import op

revision: str = '8773e87dd92a'
down_revision: str | None = 'b8fc7df2da0c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# CONVENTIONS.md rule #2: approved records are immutable. analysis_items
# is always-append-only, like audit_events (reuses reject_update_delete()
# from 6741d4c91229). obligations/cost_templates/predicates are all
# bitemporal (BitemporalMixin) — a "correction" is a new row with the old
# one's valid_to closed, not a mutation, so their triggers use the same
# narrow one-column exception as entity_profiles_reject_mutation
# (6741d4c91229): once locked, only valid_to going from NULL to a
# timestamp is allowed, nothing else.
#
# obligations/predicates are mutable *until* approved — a draft under
# expert review is normal editing, not a "correction to an approved
# record". cost_templates has no draft state (every attach is
# immediately current), so its exception applies unconditionally.
_APPEND_ONLY_TABLES = ("analysis_items",)

_REJECT_FUNCTION = "reject_update_delete"
_OBLIGATION_FUNCTION = "reject_obligation_mutation_after_approval"
_PREDICATE_FUNCTION = "reject_predicate_mutation_after_approval"
_COST_TEMPLATE_FUNCTION = "reject_cost_template_mutation"


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

    _exec(
        f"""
        CREATE FUNCTION {_OBLIGATION_FUNCTION}() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.approved IS TRUE THEN
                    RAISE EXCEPTION
                        'approved obligations cannot be deleted (see docs/CONVENTIONS.md rule 2)';
                END IF;
                RETURN OLD;
            END IF;
            IF OLD.approved IS TRUE AND (
                NEW.id IS DISTINCT FROM OLD.id OR
                NEW.clause_id IS DISTINCT FROM OLD.clause_id OR
                NEW.summary IS DISTINCT FROM OLD.summary OR
                NEW.obligation_type IS DISTINCT FROM OLD.obligation_type OR
                NEW.fields IS DISTINCT FROM OLD.fields OR
                NEW.confidence IS DISTINCT FROM OLD.confidence OR
                NEW.extracted_by IS DISTINCT FROM OLD.extracted_by OR
                NEW.approved IS DISTINCT FROM OLD.approved OR
                NEW.approved_by_user_id IS DISTINCT FROM OLD.approved_by_user_id OR
                NEW.approved_at IS DISTINCT FROM OLD.approved_at OR
                NEW.valid_from IS DISTINCT FROM OLD.valid_from OR
                NEW.recorded_at IS DISTINCT FROM OLD.recorded_at OR
                OLD.valid_to IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'approved obligations are immutable except closing valid_to for a correction (see docs/CONVENTIONS.md rule 2)';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    _exec(
        f"""
        CREATE TRIGGER obligations_reject_mutation_after_approval
        BEFORE UPDATE OR DELETE ON obligations
        FOR EACH ROW EXECUTE FUNCTION {_OBLIGATION_FUNCTION}();
        """
    )

    _exec(
        f"""
        CREATE FUNCTION {_PREDICATE_FUNCTION}() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.status = 'APPROVED' THEN
                    RAISE EXCEPTION
                        'approved predicates cannot be deleted (see docs/CONVENTIONS.md rule 2)';
                END IF;
                RETURN OLD;
            END IF;
            IF OLD.status = 'APPROVED' THEN
                RAISE EXCEPTION
                    'approved predicates are immutable — draft a new predicate for the obligation instead (see docs/CONVENTIONS.md rule 2)';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    _exec(
        f"""
        CREATE TRIGGER predicates_reject_mutation_after_approval
        BEFORE UPDATE OR DELETE ON predicates
        FOR EACH ROW EXECUTE FUNCTION {_PREDICATE_FUNCTION}();
        """
    )

    _exec(
        f"""
        CREATE FUNCTION {_COST_TEMPLATE_FUNCTION}() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION
                    'cost_templates rows are immutable and cannot be deleted (see docs/CONVENTIONS.md rule 2)';
            END IF;
            IF
                NEW.id IS DISTINCT FROM OLD.id OR
                NEW.obligation_id IS DISTINCT FROM OLD.obligation_id OR
                NEW.name IS DISTINCT FROM OLD.name OR
                NEW.drivers IS DISTINCT FROM OLD.drivers OR
                NEW.formula IS DISTINCT FROM OLD.formula OR
                NEW.currency IS DISTINCT FROM OLD.currency OR
                NEW.source_basis IS DISTINCT FROM OLD.source_basis OR
                NEW.maturity_tier IS DISTINCT FROM OLD.maturity_tier OR
                NEW.valid_from IS DISTINCT FROM OLD.valid_from OR
                NEW.recorded_at IS DISTINCT FROM OLD.recorded_at OR
                OLD.valid_to IS NOT NULL
            THEN
                RAISE EXCEPTION
                    'cost_templates rows are immutable except closing valid_to when superseded by a new version (see docs/CONVENTIONS.md rule 2)';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    _exec(
        f"""
        CREATE TRIGGER cost_templates_reject_mutation
        BEFORE UPDATE OR DELETE ON cost_templates
        FOR EACH ROW EXECUTE FUNCTION {_COST_TEMPLATE_FUNCTION}();
        """
    )


def downgrade() -> None:
    _exec("DROP TRIGGER IF EXISTS cost_templates_reject_mutation ON cost_templates;")
    _exec(f"DROP FUNCTION IF EXISTS {_COST_TEMPLATE_FUNCTION}();")
    _exec("DROP TRIGGER IF EXISTS predicates_reject_mutation_after_approval ON predicates;")
    _exec(f"DROP FUNCTION IF EXISTS {_PREDICATE_FUNCTION}();")
    _exec("DROP TRIGGER IF EXISTS obligations_reject_mutation_after_approval ON obligations;")
    _exec(f"DROP FUNCTION IF EXISTS {_OBLIGATION_FUNCTION}();")
    for table in _APPEND_ONLY_TABLES:
        _exec(f"DROP TRIGGER IF EXISTS {table}_reject_update_delete ON {table};")

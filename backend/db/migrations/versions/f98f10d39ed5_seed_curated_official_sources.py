"""seed curated official sources

Revision ID: f98f10d39ed5
Revises: 8890b8bcf773
Create Date: 2026-07-12 19:41:05.821083

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f98f10d39ed5"
down_revision: str | None = "8890b8bcf773"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_curated_sources = sa.table(
    "curated_sources",
    sa.column("key", sa.String),
    sa.column("name", sa.String),
    sa.column("url", sa.String),
)

# F9's four curated official sources. Unmapped to an instrument (that
# link is set by staff once a source is paired with a specific onboarded
# regulation) — the sweep skips versioning for unmapped sources and just
# tracks their content hash.
_SEED_ROWS = [
    {
        "key": "fca_handbook",
        "name": "FCA Handbook",
        "url": "https://www.handbook.fca.org.uk/",
    },
    {
        "key": "pra_rulebook",
        "name": "PRA Rulebook",
        "url": "https://www.prarulebook.co.uk/",
    },
    {
        "key": "legislation_gov_uk",
        "name": "legislation.gov.uk",
        "url": "https://www.legislation.gov.uk/",
    },
    {
        "key": "uk_parliament_api",
        "name": "UK Parliament API",
        "url": "https://www.parliament.uk/",
    },
]


def upgrade() -> None:
    op.bulk_insert(_curated_sources, _SEED_ROWS)


def downgrade() -> None:
    keys = ", ".join(f"'{row['key']}'" for row in _SEED_ROWS)
    op.execute(f"DELETE FROM curated_sources WHERE key IN ({keys})")

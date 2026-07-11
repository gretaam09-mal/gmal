#!/usr/bin/env python3
"""Enable Postgres extensions the schema needs, before migrations run.

Local dev creates these once by hand (see docs/runbooks/local-development.md).
Managed hosts (e.g. Render) don't pre-enable pgvector, and provisioning a
database there doesn't give you a shell to run CREATE EXTENSION yourself —
this script is the deploy-time equivalent, safe to run on every startup
(CREATE EXTENSION IF NOT EXISTS is a no-op once it's already enabled).
"""

from sqlalchemy import text

from api.config import get_settings
from db.session import get_engine


def main() -> None:
    with get_engine().begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    print(f"Extensions ensured on {get_settings().database_url.split('@')[-1]}")


if __name__ == "__main__":
    main()

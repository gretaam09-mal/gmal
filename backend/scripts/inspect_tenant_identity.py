#!/usr/bin/env python3
"""Read-only diagnostic for "my assessments keep disappearing": prints
every User row for an email, every Tenant that identity can act in (as
creator or member — the same query GET /tenants uses, see
api/routes/tenants.py::list_my_tenants), and how many workspaces
("assessments") sit in each. Makes no writes.

This does not merge or delete anything — it exists so a duplicate/
orphaned tenant situation (the bug this diagnoses) is visible before
anyone decides what, if anything, to consolidate by hand.

Usage (run against whichever database PROVISION_DATABASE_URL points at —
for the deployed app that means running this from a Render shell, since
the database is not reachable from outside Render's network):

    poetry run python -m scripts.inspect_tenant_identity someone@example.com
"""

import argparse

from sqlalchemy import func, select

from db.models import Membership, MembershipStatus, Tenant, User, Workspace
from db.session import raw_session, set_user_context


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Email to look up (case-sensitive, matches User.email)")
    args = parser.parse_args()

    with raw_session() as session:
        users = session.execute(select(User).where(User.email == args.email)).scalars().all()
        if not users:
            print(f"No User row for {args.email!r}.")
            print(
                "If they've definitely signed in before, check for a case "
                "mismatch or a Clerk-side email change — User.email is unique "
                "and exact-match here."
            )
            return

        print(f"{len(users)} User row(s) for {args.email!r}:")
        for user in users:
            print(
                f"  - id={user.id}  clerk_user_id={user.clerk_user_id!r}  "
                f"is_staff={user.is_staff}"
            )

        for user in users:
            print(f"\n=== Tenants reachable by user {user.id} ({user.email}) ===")
            set_user_context(session, user.id)
            member_tenant_ids = list(
                session.execute(
                    select(Membership.tenant_id).where(
                        Membership.user_id == user.id,
                        Membership.status == MembershipStatus.ACTIVE,
                    )
                ).scalars()
            )
            tenants = (
                session.execute(
                    select(Tenant)
                    .where(
                        (Tenant.created_by_user_id == user.id) | (Tenant.id.in_(member_tenant_ids))
                    )
                    .order_by(Tenant.created_at)
                )
                .scalars()
                .all()
            )
            if not tenants:
                print("  (none — this identity has never created or joined an organisation)")
                continue
            for tenant in tenants:
                workspace_count = session.execute(
                    select(func.count(Workspace.id)).where(Workspace.tenant_id == tenant.id)
                ).scalar_one()
                created_by_this_user = tenant.created_by_user_id == user.id
                role = "creator" if created_by_this_user else "member"
                print(
                    f"  - tenant={tenant.id}  name={tenant.name!r}  slug={tenant.slug!r}  "
                    f"created_at={tenant.created_at}  role={role}  "
                    f"workspaces(assessments)={workspace_count}"
                )


if __name__ == "__main__":
    main()

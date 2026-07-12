#!/usr/bin/env python3
"""Grant a user staff access to the F3 instrument-onboarding workbench.

Nobody is staff by default (User.is_staff defaults False, see
db/models/tenancy.py) — there's no self-serve way to become staff, by
design. This is the one-off, run-by-hand equivalent of a real admin
console, for internal use only. Usage:

    poetry run python -m scripts.grant_staff someone@example.com
"""

import argparse

from sqlalchemy import select

from db.models import User
from db.session import raw_session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Email of an existing User row to grant staff access to")
    parser.add_argument("--revoke", action="store_true", help="Revoke staff access instead")
    args = parser.parse_args()

    with raw_session() as session:
        user = session.execute(select(User).where(User.email == args.email)).scalar_one_or_none()
        if user is None:
            raise SystemExit(
                f"No user found with email {args.email!r} — they must sign in once first"
            )
        user.is_staff = not args.revoke
        session.commit()
        verb = "Revoked" if args.revoke else "Granted"
        print(f"{verb} staff access for {args.email}")


if __name__ == "__main__":
    main()

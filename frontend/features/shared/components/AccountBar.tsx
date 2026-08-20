"use client";

import { useClerk, useUser } from "@clerk/nextjs";
import Link from "next/link";

import { Button } from "@/design-system/components/button";

/**
 * The one place a signed-in user can see their email, reach the staff-only
 * /admin workbench, and sign out — rendered in both the dashboard header
 * (features/workspaces/components/WorkspaceDashboard.tsx) and the admin
 * top bar (features/admin/components/StaffGate.tsx) so neither is only
 * reachable by typing a URL or editing one.
 */
export function AccountBar({ isStaff }: { isStaff: boolean }) {
  const { signOut } = useClerk();
  const { user } = useUser();
  const email = user?.primaryEmailAddress?.emailAddress ?? "";

  return (
    <div className="flex items-center gap-3">
      {isStaff ? (
        <Link href="/admin" className="font-ui text-sm text-primary-navy hover:underline">
          Instrument workbench
        </Link>
      ) : null}
      {email ? <span className="font-ui text-xs text-ink/50">{email}</span> : null}
      <Button variant="outline" size="dense" onClick={() => signOut({ redirectUrl: "/" })}>
        Sign out
      </Button>
    </div>
  );
}

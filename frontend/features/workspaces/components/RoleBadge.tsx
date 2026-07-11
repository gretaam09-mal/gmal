import { cn } from "@/lib/utils";

import type { Role } from "../types";

const ROLE_STYLES: Record<Role, string> = {
  owner: "bg-primary-navy text-paper",
  approver: "bg-ink text-paper",
  analyst: "bg-ink/10 text-ink",
  viewer: "bg-ink/5 text-ink/70",
};

export function RoleBadge({ role }: { role: Role }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 font-ui text-xs font-medium capitalize",
        ROLE_STYLES[role],
      )}
    >
      {role}
    </span>
  );
}

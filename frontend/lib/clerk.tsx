import type { ReactNode } from "react";

import { ClerkProvider } from "@clerk/nextjs";

const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export const clerkConfigured = Boolean(publishableKey);

/**
 * Wraps children in ClerkProvider only when a real Clerk application is
 * configured. Until then (dev/CI without keys — see
 * docs/runbooks/clerk-setup.md) this is a passthrough, so routes that
 * don't need auth (marketing) never require Clerk to be set up, and
 * routes that do (see middleware.ts) show a clear "not configured"
 * state instead of crashing.
 */
export function ConditionalClerkProvider({ children }: { children: ReactNode }) {
  if (!publishableKey) {
    return <>{children}</>;
  }
  return <ClerkProvider publishableKey={publishableKey}>{children}</ClerkProvider>;
}

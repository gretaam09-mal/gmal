import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

// (app) -> /dashboard(.*), (admin) -> /admin(.*) — see app/(app) and app/(admin).
const isProtectedRoute = createRouteMatcher(["/dashboard(.*)", "/admin(.*)"]);

const clerkConfigured = Boolean(
  process.env.CLERK_SECRET_KEY && process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
);

// Until a Clerk application exists (docs/runbooks/clerk-setup.md), this is a
// passthrough rather than enforcing auth, so the marketing site and CI keep
// working without real keys. The (app)/(admin) route groups are unprotected
// in that state — that's expected pre-launch, not a bypass of anything live.
export default clerkConfigured
  ? clerkMiddleware(async (auth, req) => {
      if (isProtectedRoute(req)) {
        await auth.protect();
      }
      // A signed-in visitor hitting the marketing page has nothing to do
      // there — send them straight to the dashboard instead of making them
      // find their own way back in.
      if (req.nextUrl.pathname === "/") {
        const { userId } = await auth();
        if (userId) {
          return NextResponse.redirect(new URL("/dashboard", req.url));
        }
      }
    })
  : () => NextResponse.next();

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};

import { redirect } from "next/navigation";

// /dashboard is the one canonical URL for the signed-in app shell (see
// app/(app)/dashboard/page.tsx) — this exists only because "/app" is a
// plausible guess for that URL and used to 404.
export default function AppRedirectPage() {
  redirect("/dashboard");
}

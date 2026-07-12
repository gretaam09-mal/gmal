"use client";

import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getMe } from "@/lib/me";

type Status = "checking" | "allowed" | "denied";

/**
 * The only thing standing between /admin and any signed-in user —
 * middleware.ts only checks "is someone signed in", not "are they
 * staff". Never linked from the client-facing UI regardless (see
 * db/models/tenancy.py::User.is_staff), this is defense in depth so a
 * non-staff user who guesses the URL gets redirected, not a raw 403 page.
 */
export function StaffGate({ children }: { children: React.ReactNode }) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const router = useRouter();
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      router.replace("/sign-in");
      return;
    }
    getMe(getToken)
      .then((me) => setStatus(me.is_staff ? "allowed" : "denied"))
      .catch(() => setStatus("denied"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoaded, isSignedIn]);

  useEffect(() => {
    if (status === "denied") router.replace("/");
  }, [status, router]);

  if (status !== "allowed") {
    return (
      <main className="flex min-h-screen items-center justify-center p-8">
        <p className="font-ui text-sm text-ink/60">
          {status === "checking" ? "Checking access…" : "Redirecting…"}
        </p>
      </main>
    );
  }

  return <>{children}</>;
}

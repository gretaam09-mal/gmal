import { SignIn } from "@clerk/nextjs";

import { clerkConfigured } from "@/lib/clerk";

export default function SignInPage() {
  if (!clerkConfigured) {
    return (
      <p className="font-ui text-sm text-ink/70">
        Sign-in isn&apos;t configured yet — see docs/runbooks/clerk-setup.md.
      </p>
    );
  }
  return <SignIn />;
}

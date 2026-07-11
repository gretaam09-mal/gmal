import { SignUp } from "@clerk/nextjs";

import { clerkConfigured } from "@/lib/clerk";

export default function SignUpPage() {
  if (!clerkConfigured) {
    return (
      <p className="font-ui text-sm text-ink/70">
        Sign-up isn&apos;t configured yet — see docs/runbooks/clerk-setup.md.
      </p>
    );
  }
  return <SignUp />;
}

import Link from "next/link";

import { Button } from "@/design-system/components/button";

export default function MarketingHomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="font-ui text-3xl font-semibold text-ink">Provision</h1>
      <p className="max-w-md font-document text-ink/70">
        Expert-reviewed, quantified regulatory-exposure memos for deal teams.
      </p>
      <Link href="/sign-in">
        <Button size="comfortable">Sign in</Button>
      </Link>
    </main>
  );
}

import { WorkspaceDashboard } from "@/features/workspaces/components/WorkspaceDashboard";
import { clerkConfigured } from "@/lib/clerk";

export default function DashboardPage() {
  if (!clerkConfigured) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center p-8">
        <p className="font-ui text-ink">
          Authentication isn&apos;t configured yet — see docs/runbooks/clerk-setup.md.
        </p>
      </main>
    );
  }
  return <WorkspaceDashboard />;
}

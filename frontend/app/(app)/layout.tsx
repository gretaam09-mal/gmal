import { ConditionalClerkProvider } from "@/lib/clerk";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <ConditionalClerkProvider>
      <div data-route-group="app" className="min-h-screen bg-paper">
        {children}
      </div>
    </ConditionalClerkProvider>
  );
}

import { ConditionalClerkProvider } from "@/lib/clerk";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ConditionalClerkProvider>
      <div data-route-group="admin" className="min-h-screen bg-paper">
        {children}
      </div>
    </ConditionalClerkProvider>
  );
}

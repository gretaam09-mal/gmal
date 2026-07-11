import { ConditionalClerkProvider } from "@/lib/clerk";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <ConditionalClerkProvider>
      <div
        data-route-group="auth"
        className="flex min-h-screen flex-col items-center justify-center bg-paper p-8"
      >
        {children}
      </div>
    </ConditionalClerkProvider>
  );
}

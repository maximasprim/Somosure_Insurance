import { AppNav } from "@/components/AppNav";
import { AuthGuard } from "@/components/AuthGuard";

/**
 * Shared shell for the logged-in customer area. (customer) is a Next.js
 * route group - it groups /dashboard, /profile, /claims, /support under
 * one layout without changing any of their URLs. AuthGuard sends anyone
 * without a valid, unexpired session to /login before any of them render.
 */
export default function CustomerLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="min-h-screen bg-white">
        <AppNav />
        {children}
      </div>
    </AuthGuard>
  );
}
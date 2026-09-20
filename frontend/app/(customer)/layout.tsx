import { AppNav } from "@/components/AppNav";

/**
 * Shared shell for the logged-in customer area. (customer) is a Next.js
 * route group - it groups /dashboard, /profile, /claims, /support under
 * one layout without changing any of their URLs. Each page still does
 * its own isLoggedIn() redirect; this layout only adds the persistent
 * nav around them.
 */
export default function CustomerLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white">
      <AppNav />
      {children}
    </div>
  );
}

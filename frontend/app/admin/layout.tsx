import { AdminSidebar } from "@/components/AdminSidebar";
import { AuthGuard } from "@/components/AuthGuard";

/**
 * Shared shell for every /admin/* route. Because Next.js applies a
 * segment's layout.tsx to all of its nested pages automatically, adding
 * this one file gives every existing admin page (applications, claims,
 * financing, leads, providers, rate-cards, reports, search, stickers,
 * whatsapp, automation) a consistent sidebar/nav with zero edits to any
 * of them, and any future /admin/* page gets it automatically too.
 *
 * AuthGuard is what actually protects this section - none of the admin
 * pages checked login state on their own, and a couple (the /admin
 * landing page, /admin/search) make no API call at all, so they'd
 * otherwise render fully for a signed-out visitor.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-col bg-neutral/40 md:flex-row">
        <AdminSidebar />
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </AuthGuard>
  );
}
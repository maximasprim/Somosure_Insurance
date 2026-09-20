import { AdminSidebar } from "@/components/AdminSidebar";

/**
 * Shared shell for every /admin/* route. Because Next.js applies a
 * segment's layout.tsx to all of its nested pages automatically, adding
 * this one file gives every existing admin page (applications, claims,
 * financing, leads, providers, rate-cards, reports, search, stickers,
 * whatsapp, automation) a consistent sidebar/nav with zero edits to any
 * of them, and any future /admin/* page gets it automatically too.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-neutral/40 md:flex-row">
      <AdminSidebar />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

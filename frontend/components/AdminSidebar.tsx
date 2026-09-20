"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Users,
  FileText,
  ShieldAlert,
  Banknote,
  Building2,
  Percent,
  Zap,
  Tag,
  MessageCircle,
  BarChart3,
  Search,
  Menu,
  X,
  LogOut,
  Home,
} from "lucide-react";
import { clearSession, getTokenRole } from "@/lib/api";
import Image from "next/image";
import SomosureLogo from "@/assets/somosure_logo.png";

interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    title: "Sales & CRM",
    items: [
      { label: "Leads", href: "/admin/leads", icon: Users },
      { label: "Applications", href: "/admin/applications", icon: FileText },
    ],
  },
  {
    title: "Underwriting",
    items: [
      { label: "Claims", href: "/admin/claims", icon: ShieldAlert },
      { label: "Financing", href: "/admin/financing", icon: Banknote },
      { label: "Providers", href: "/admin/providers", icon: Building2 },
      { label: "Rate cards", href: "/admin/rate-cards", icon: Percent },
    ],
  },
  {
    title: "Operations",
    items: [
      { label: "Automation", href: "/admin/automation", icon: Zap },
      { label: "Stickers", href: "/admin/stickers", icon: Tag },
      { label: "WhatsApp", href: "/admin/whatsapp", icon: MessageCircle },
    ],
  },
  {
    title: "Insights",
    items: [
      { label: "Reports", href: "/admin/reports", icon: BarChart3 },
      { label: "Search", href: "/admin/search", icon: Search },
    ],
  },
];

function isActive(pathname: string | null, href: string) {
  if (!pathname) return false;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavLinks({ pathname, onNavigate }: { pathname: string | null; onNavigate?: () => void }) {
  return (
    <div className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4">
      <Link
        href="/admin"
        onClick={onNavigate}
        className={`flex items-center gap-2.5 rounded-control px-3 py-2 text-sm font-semibold ${pathname === "/admin" ? "bg-brand-tint text-ink" : "text-ink-soft hover:bg-neutral hover:text-ink"
          }`}
      >
        <LayoutDashboard className="h-4 w-4" /> Overview
      </Link>

      {SECTIONS.map((section) => (
        <div key={section.title}>
          <p className="px-3 pb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-soft/70">{section.title}</p>
          <div className="flex flex-col gap-0.5">
            {section.items.map((item) => {
              const Icon = item.icon;
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  className={`flex items-center gap-2.5 rounded-control px-3 py-2 text-sm font-medium transition-colors ${active ? "bg-brand-tint text-ink" : "text-ink-soft hover:bg-neutral hover:text-ink"
                    }`}
                >
                  <Icon className="h-4 w-4" /> {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Shared shell for every /admin/* page (see app/admin/layout.tsx). Before
 * this, each of the 12+ admin pages was a bare <main> with no link to any
 * other admin section - staff had to know/bookmark every URL by hand.
 */
export function AdminSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const role = typeof window !== "undefined" ? getTokenRole() : null;

  function handleLogout() {
    clearSession();
    router.push("/login");
  }

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-neutral-border bg-white md:flex">
        <div className="flex items-center justify-between border-b border-neutral-border px-5 py-3">
          <Link href="/" className="font-display text-lg font-extrabold tracking-tight">
            {/* Somosure */}
            <div className="relative inline-block">
              <div
                aria-hidden
                className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{
                  width: "220%",
                  height: "220%",
                  background:
                    "radial-gradient(circle, rgba(255,204,0,0.95) 0%, rgba(255,204,0,0.55) 30%, rgba(255,204,0,0.20) 55%, transparent 72%)",
                  filter: "blur(14px)",
                  zIndex: 0,
                }}
              />
              <Image
                src={SomosureLogo}
                alt="Somosure"
                className="relative z-10 h-6 md:h-8 w-auto"
                priority
              />
            </div>
          </Link>
        </div>
        <NavLinks pathname={pathname} />
        <div className="border-t border-neutral-border px-3 py-3">
          {role && <p className="px-3 pb-2 text-xs text-ink-soft">Signed in - {role.replace(/_/g, " ")}</p>}
          <Link href="/" className="flex items-center gap-2.5 rounded-control px-3 py-2 text-sm font-medium text-ink-soft hover:bg-neutral hover:text-ink">
            <Home className="h-4 w-4" /> Back to site
          </Link>
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-2.5 rounded-control px-3 py-2 text-left text-sm font-medium text-ink-soft hover:bg-neutral hover:text-ink"
          >
            <LogOut className="h-4 w-4" /> Log out
          </button>
        </div>
      </aside>

      {/* Mobile top bar + drawer */}
      <div className="sticky top-0 z-40 flex items-center justify-between border-b border-neutral-border bg-white px-4 py-3 md:hidden">
        <Link href="/admin" className="font-display text-base font-extrabold tracking-tight">
          Somosure <span className="font-normal text-ink-soft">Admin</span>
        </Link>
        <button onClick={() => setMobileOpen(true)} className="rounded-control p-2 text-ink" aria-label="Open menu">
          <Menu className="h-6 w-6" />
        </button>
      </div>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-ink/40 md:hidden"
            onClick={() => setMobileOpen(false)}
          >
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "tween", duration: 0.25 }}
              className="flex h-full w-72 flex-col bg-white"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-neutral-border px-5 py-4">
                <span className="font-display text-base font-extrabold">Somosure Admin</span>
                <button onClick={() => setMobileOpen(false)} aria-label="Close menu">
                  <X className="h-6 w-6" />
                </button>
              </div>
              <NavLinks pathname={pathname} onNavigate={() => setMobileOpen(false)} />
              <div className="border-t border-neutral-border px-3 py-3">
                <Link href="/" onClick={() => setMobileOpen(false)} className="flex items-center gap-2.5 rounded-control px-3 py-2 text-sm font-medium hover:bg-neutral">
                  <Home className="h-4 w-4" /> Back to site
                </Link>
                <button
                  onClick={() => {
                    setMobileOpen(false);
                    handleLogout();
                  }}
                  className="flex w-full items-center gap-2.5 rounded-control px-3 py-2 text-left text-sm font-medium text-status-error hover:bg-neutral"
                >
                  <LogOut className="h-4 w-4" /> Log out
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

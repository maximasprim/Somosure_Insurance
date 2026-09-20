"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { LayoutDashboard, FileText, LifeBuoy, User, Menu, X, LogOut, Home } from "lucide-react";
import { clearSession } from "@/lib/api";

const LINKS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Get a quote", href: "/quote/motor", icon: FileText },
  { label: "Claims", href: "/claims", icon: FileText },
  { label: "Support", href: "/support", icon: LifeBuoy },
  { label: "Profile", href: "/profile", icon: User },
];

/**
 * Persistent top nav for the logged-in customer area (dashboard, profile,
 * claims, support - see app/(customer)/layout.tsx). Before this, each of
 * these pages rendered a bare <main> with no way to reach any of the
 * others except the browser back button.
 */
export function AppNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  function handleLogout() {
    clearSession();
    router.push("/login");
  }

  return (
    <nav className="sticky top-0 z-40 border-b border-neutral-border bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5 md:px-12">
        <div className="flex items-center gap-8">
          <Link href="/" className="font-display text-base font-extrabold tracking-tight">
            Somosure
          </Link>
          <div className="hidden items-center gap-1 md:flex">
            {LINKS.map((l) => {
              const active = pathname === l.href || (l.href !== "/dashboard" && pathname?.startsWith(l.href));
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={`rounded-control px-3 py-2 text-sm font-medium transition-colors ${
                    active ? "bg-brand-tint text-ink" : "text-ink-soft hover:bg-neutral hover:text-ink"
                  }`}
                >
                  {l.label}
                </Link>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/" className="hidden text-sm font-medium text-ink-soft hover:text-ink md:flex md:items-center md:gap-1.5">
            <Home className="h-4 w-4" /> Back to site
          </Link>
          <button
            onClick={handleLogout}
            className="hidden items-center gap-1.5 rounded-control px-3 py-2 text-sm font-medium text-ink-soft hover:bg-neutral hover:text-ink md:flex"
          >
            <LogOut className="h-4 w-4" /> Log out
          </button>
          <button onClick={() => setMobileOpen(true)} className="rounded-control p-2 text-ink md:hidden" aria-label="Open menu">
            <Menu className="h-6 w-6" />
          </button>
        </div>
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
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "tween", duration: 0.25 }}
              className="ml-auto flex h-full w-72 flex-col gap-1 bg-white p-6"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="mb-4 flex items-center justify-between">
                <span className="font-display text-lg font-extrabold">Somosure</span>
                <button onClick={() => setMobileOpen(false)} aria-label="Close menu">
                  <X className="h-6 w-6" />
                </button>
              </div>
              {LINKS.map((l) => {
                const Icon = l.icon;
                const active = pathname === l.href || (l.href !== "/dashboard" && pathname?.startsWith(l.href));
                return (
                  <Link
                    key={l.href}
                    href={l.href}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center gap-2.5 rounded-control px-2 py-2.5 text-sm font-medium ${
                      active ? "bg-brand-tint text-ink" : "hover:bg-neutral"
                    }`}
                  >
                    <Icon className="h-4 w-4" /> {l.label}
                  </Link>
                );
              })}
              <div className="my-3 border-t border-neutral-border" />
              <Link href="/" onClick={() => setMobileOpen(false)} className="flex items-center gap-2.5 rounded-control px-2 py-2.5 text-sm font-medium hover:bg-neutral">
                <Home className="h-4 w-4" /> Back to site
              </Link>
              <button
                onClick={() => {
                  setMobileOpen(false);
                  handleLogout();
                }}
                className="flex items-center gap-2.5 rounded-control px-2 py-2.5 text-left text-sm font-medium text-status-error hover:bg-neutral"
              >
                <LogOut className="h-4 w-4" /> Log out
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}

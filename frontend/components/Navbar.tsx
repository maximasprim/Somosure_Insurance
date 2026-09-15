"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/Button";

const INSURANCE_LINKS = [
  { label: "Motor", href: "/quote/motor" },
  { label: "Medical", href: "/quote/medical" },
  { label: "Life", href: "/quote/life" },
  { label: "Home", href: "/quote/home" },
  { label: "Travel", href: "/quote/travel" },
  { label: "Business", href: "/quote/business" },
  { label: "Personal accident", href: "/quote/personal_accident" },
];

const NAV_LINKS = [
  { label: "Claims", href: "/claims" },
  { label: "Renewals", href: "/renewals" },
  { label: "About", href: "/about" },
  { label: "Resources", href: "/resources" },
  { label: "FAQ", href: "/faq" },
];

export function Navbar() {
  const [insuranceOpen, setInsuranceOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav
      className={`sticky top-0 z-40 border-b transition-colors ${
        scrolled ? "border-neutral-border bg-white/90 backdrop-blur" : "border-transparent bg-white/60 backdrop-blur-sm"
      }`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4 md:px-12">
        <Link href="/" className="font-display text-lg font-extrabold tracking-tight">
          Somosure
        </Link>

        <div className="hidden items-center gap-8 text-sm font-medium text-ink-soft md:flex">
          <div
            className="relative"
            onMouseEnter={() => setInsuranceOpen(true)}
            onMouseLeave={() => setInsuranceOpen(false)}
          >
            <Link href="/insurance" className="flex items-center gap-1 hover:text-ink">
              Insurance <ChevronDown className="h-3.5 w-3.5" />
            </Link>
            <AnimatePresence>
              {insuranceOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 8 }}
                  transition={{ duration: 0.15 }}
                  className="absolute left-0 top-full w-56 rounded-card border border-neutral-border bg-white p-2 shadow-card"
                >
                  {INSURANCE_LINKS.map((l) => (
                    <Link
                      key={l.href}
                      href={l.href}
                      className="block rounded-control px-3 py-2 text-sm text-ink hover:bg-neutral"
                    >
                      {l.label}
                    </Link>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          {NAV_LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="hover:text-ink">
              {l.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="hidden text-sm font-medium text-ink-soft hover:text-ink md:block">
            My account
          </Link>
          <Link href="/quote/motor" className="hidden md:block">
            <Button size="md">Get a quote</Button>
          </Link>
          <button
            onClick={() => setMobileOpen(true)}
            className="rounded-control p-2 text-ink md:hidden"
            aria-label="Open menu"
          >
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
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-soft">Insurance</p>
              {INSURANCE_LINKS.map((l) => (
                <Link key={l.href} href={l.href} onClick={() => setMobileOpen(false)} className="rounded-control px-2 py-2.5 text-sm font-medium hover:bg-neutral">
                  {l.label}
                </Link>
              ))}
              <div className="my-3 border-t border-neutral-border" />
              {NAV_LINKS.map((l) => (
                <Link key={l.href} href={l.href} onClick={() => setMobileOpen(false)} className="rounded-control px-2 py-2.5 text-sm font-medium hover:bg-neutral">
                  {l.label}
                </Link>
              ))}
              <div className="mt-auto flex flex-col gap-2 pt-6">
                <Link href="/dashboard" onClick={() => setMobileOpen(false)}>
                  <Button variant="ghost" className="w-full">My account</Button>
                </Link>
                <Link href="/quote/motor" onClick={() => setMobileOpen(false)}>
                  <Button className="w-full">Get a quote</Button>
                </Link>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}

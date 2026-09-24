import Link from "next/link";
import SomosureLogo from "@/assets/somosure_logo.png";
import Image from "next/image";

const COLUMNS = [
  {
    title: "Insurance",
    links: [
      { label: "Motor", href: "/quote/motor" },
      { label: "Medical", href: "/quote/medical" },
      { label: "Life", href: "/quote/life" },
      { label: "Home", href: "/quote/home" },
      { label: "Travel", href: "/quote/travel" },
      { label: "Business", href: "/quote/business" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About Somosure", href: "/about" },
      { label: "How it works", href: "/insurance" },
      { label: "Renewals", href: "/renewals" },
    ],
  },
  {
    title: "Support",
    links: [
      { label: "FAQ", href: "/faq" },
      { label: "Claims", href: "/claims" },
      { label: "Resources", href: "/resources" },
      { label: "Contact us", href: "/contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy policy", href: "/privacy" },
      { label: "Terms of service", href: "/terms" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-neutral-border bg-neutral">
      <div className="mx-auto max-w-8xl px-2 py-2 mt-12 md:px-4">
        <div className="grid gap-10 sm:grid-cols-2 md:grid-cols-5">
       <div className="relative items-center justify-center sm:col-span-2 md:col-span-1">
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
      className="relative z-10 h-8 md:h-12 w-auto"
      priority
    />
  </div>
  <p className="mt-3 max-w-[26ch] text-sm text-ink-soft">
    Insurance Made Simpler - compare, buy, and manage cover from one trusted platform.
  </p>
</div>

          {COLUMNS.map((col) => (
            <div key={col.title}>
              <h3 className="text-sm font-semibold text-ink">{col.title}</h3>
              <ul className="mt-3 flex flex-col gap-2">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-ink-soft hover:text-ink">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-start justify-between gap-4 border-t border-neutral-border pt-6 text-xs text-ink-soft sm:flex-row sm:items-center">
          <p>© {new Date().getFullYear()} Somosure Insurance. All rights reserved.</p>
          <p>Nairobi, Kenya</p>
        </div>
      </div>
    </footer>
  );
}

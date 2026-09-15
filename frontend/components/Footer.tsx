import Link from "next/link";

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
      <div className="mx-auto max-w-6xl px-6 py-14 md:px-12">
        <div className="grid gap-10 sm:grid-cols-2 md:grid-cols-5">
          <div className="sm:col-span-2 md:col-span-1">
            <span className="font-display text-lg font-extrabold tracking-tight">Somosure</span>
            <p className="mt-3 max-w-[26ch] text-sm text-ink-soft">
              Insurance made simpler - compare, buy, and manage cover from one trusted platform.
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

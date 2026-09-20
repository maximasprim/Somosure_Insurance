import Link from "next/link";

/**
 * Minimal header for /login and /register - just enough to get back to
 * the marketing site and to cross-link the two auth pages. Before this,
 * both pages were an isolated <main> with literally no way out except
 * the browser back button.
 */
export function AuthTopbar({ crossLinkHref, crossLinkLabel }: { crossLinkHref: string; crossLinkLabel: string }) {
  return (
    <div className="mx-auto flex max-w-md items-center justify-between px-6 pt-8">
      <Link href="/" className="font-display text-lg font-extrabold tracking-tight">
        Somosure
      </Link>
      <Link href={crossLinkHref} className="text-sm font-medium text-ink-soft hover:text-ink">
        {crossLinkLabel}
      </Link>
    </div>
  );
}

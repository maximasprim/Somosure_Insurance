import Link from "next/link";
import SomosureLogo from "@/assets/somosure_logo.png";
import Image from "next/image";

/**
 * Minimal header for /login and /register - just enough to get back to
 * the marketing site and to cross-link the two auth pages. Before this,
 * both pages were an isolated <main> with literally no way out except
 * the browser back button.
 */
export function AuthTopbar({ crossLinkHref, crossLinkLabel }: { crossLinkHref: string; crossLinkLabel: string }) {
  return (
    <div className="flex justify-between px-8 py-2 items-center pt-3">
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
            className="relative z-10 h-8 md:h-12 w-auto"
            priority
          />
        </div>
      </Link>
      <Link href={crossLinkHref} className="text-sm font-medium text-brand hover:text-brand/80 hover:underline">
        {crossLinkLabel}
      </Link>
    </div>
  );
}
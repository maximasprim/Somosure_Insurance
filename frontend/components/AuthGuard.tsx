"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { clearSession, hasValidSession } from "@/lib/api";

/**
 * Wraps a protected route group (customer dashboard, admin) so its pages
 * never render for a visitor who isn't logged in or whose token has
 * expired - they're sent to /login instead.
 *
 * Why this lives in the layout rather than each page: a per-page
 * `if (!isLoggedIn()) redirect()` check only fires once that page happens
 * to run its own effect, so any page that forgets the check (or, like a
 * static admin landing page, never calls the API at all) is left
 * unprotected. Putting the check here means every current and future
 * route under this layout is covered automatically.
 *
 * `checked` starts false so the very first render - regardless of auth
 * state - returns null. The real check then runs client-side (localStorage
 * isn't available during server rendering anyway) and only flips the
 * screen on once a valid session is confirmed, so protected content never
 * flashes before the redirect happens. Re-running on `pathname` also
 * catches a token that expires while the user is navigating between pages
 * inside an already-mounted layout (e.g. dashboard -> profile).
 *
 * This is a UI convenience only, same as the rest of the client-side auth
 * helpers in lib/api.ts - the backend re-verifies the token on every
 * request and is the real authority.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!hasValidSession()) {
      clearSession();
      router.replace("/login");
      return;
    }
    setChecked(true);
  }, [pathname, router]);

  if (!checked) return null;
  return <>{children}</>;
}
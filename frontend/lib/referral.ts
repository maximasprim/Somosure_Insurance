// Remembers which referral / affiliate link a visitor arrived through, so the
// referrer is credited even if the customer asks for a quote first and only
// buys days later (most customers never register an account).
//
// A link looks like  https://somosure.co.ke/?ref=AFF3K9X2A . The code is kept in
// this browser for 30 days and sent along with the quote request; the server
// decides whether it can be used (new customers only, once, never your own code).

const KEY = "somosure_ref";
const TTL_MS = 30 * 24 * 60 * 60 * 1000;

export function rememberReferral(code: string): void {
  const clean = code.trim().toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 20);
  if (!clean) return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify({ code: clean, savedAt: Date.now() }));
  } catch {
    /* storage blocked - the link simply won't be remembered */
  }
}

export function getStoredReferral(): string | undefined {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as { code?: string; savedAt?: number };
    if (!parsed.code || !parsed.savedAt || Date.now() - parsed.savedAt > TTL_MS) {
      window.localStorage.removeItem(KEY);
      return undefined;
    }
    return parsed.code;
  } catch {
    return undefined;
  }
}

export function referralLink(code: string): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "https://somosure.co.ke";
  return `${origin}/?ref=${encodeURIComponent(code)}`;
}

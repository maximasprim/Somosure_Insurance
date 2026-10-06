import type { ApplicationResult, NormalizedQuote, QuoteRequestResult } from "@/lib/types";

// Save-and-resume for the quote flow: if someone closes the tab, loses
// signal or gets pulled away mid-way, they can pick up where they left off
// instead of re-typing everything.
//
// Deliberately conservative:
//  - Only the steps up to "awaiting approval" are ever saved. The payment
//    step is NEVER resumed - someone who had already paid and then came
//    back could otherwise be shown a fresh payment form and pay twice. The
//    saved session is cleared the moment the flow reaches payment.
//  - Stored in this browser only, expires after 24 hours, and the
//    "Start over" button wipes it - so a shared device doesn't keep it.
//  - Every storage call is wrapped, so private-browsing/blocked storage just
//    means "nothing to resume", never an error.

export type SavedStep = "compare" | "documents" | "awaiting_approval";

export interface SavedQuoteSession {
  category: string;
  step: SavedStep;
  result: QuoteRequestResult;
  customerId: string;
  application: ApplicationResult | null;
  selectedQuote: NormalizedQuote | null;
  savedAt: number;
}

const TTL_MS = 24 * 60 * 60 * 1000;
const key = (category: string) => `somosure_quote_session_v1_${category}`;

export function saveQuoteSession(session: Omit<SavedQuoteSession, "savedAt">): void {
  try {
    window.localStorage.setItem(key(session.category), JSON.stringify({ ...session, savedAt: Date.now() }));
  } catch {
    /* storage unavailable - nothing to resume, which is fine */
  }
}

export function loadQuoteSession(category: string): SavedQuoteSession | null {
  try {
    const raw = window.localStorage.getItem(key(category));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SavedQuoteSession;
    if (!parsed?.result?.quotes || Date.now() - parsed.savedAt > TTL_MS) {
      window.localStorage.removeItem(key(category));
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearQuoteSession(category: string): void {
  try {
    window.localStorage.removeItem(key(category));
  } catch {
    /* ignore */
  }
}

export const STEP_LABEL: Record<SavedStep, string> = {
  compare: "comparing your quotes",
  documents: "uploading your documents",
  awaiting_approval: "waiting for approval",
};

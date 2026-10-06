"use client";

import { useEffect, useState } from "react";
import { MessageCircle, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { WHATSAPP_NUMBER } from "@/components/WhatsAppButton";
import { api } from "@/lib/api";
import type { CategoryAvailability } from "@/lib/types";

/**
 * Whether a product category can be quoted online right now.
 *
 *  - Motor is never gated: it is the core product, so its form is always shown.
 *  - For every other category the backend decides (GET /api/v1/quotes/availability):
 *    a category is live only when a real, non-demo insurer or rate card can price it.
 *  - If the check fails for any reason we fail OPEN (show the normal form) -
 *    a hiccup here must never lock customers out of getting a quote.
 */
export function useCategoryAvailability(
  category: string,
  forceComingSoon = false
): "loading" | "available" | "coming_soon" {
  const [state, setState] = useState<"loading" | "available" | "coming_soon">(
    forceComingSoon ? "coming_soon" : category === "motor" ? "available" : "loading"
  );

  useEffect(() => {
    // A product flagged comingSoon in its config never asks the server (and
    // can never "fail open" into a quote form).
    if (category === "motor" || forceComingSoon) return;
    let cancelled = false;
    api
      .get<{ categories: Record<string, CategoryAvailability> }>("/api/v1/quotes/availability")
      .then((res) => {
        if (cancelled) return;
        const entry = res.categories[category];
        setState(entry && !entry.available ? "coming_soon" : "available");
      })
      .catch(() => {
        if (!cancelled) setState("available");
      });
    return () => {
      cancelled = true;
    };
  }, [category, forceComingSoon]);

  return state;
}

export function ComingSoonCard({
  category,
  productLabel,
  highlights,
}: {
  category: string;
  productLabel: string;
  highlights?: string[];
}) {
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const waText = encodeURIComponent(`Hello Somosure, I'd like to talk to an agent about ${productLabel.toLowerCase()}.`);

  async function requestCallback(e: React.FormEvent) {
    e.preventDefault();
    if (fullName.trim().length < 2 || phone.trim().length < 10) {
      setError("Please enter your name and a valid phone number so an agent can reach you.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/contact", {
        full_name: fullName.trim(),
        phone: phone.trim(),
        message: `Callback request: I'd like to talk to an agent about ${productLabel.toLowerCase()} (online quotes not yet available).`,
        product_interest: category,
      });
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong - please try WhatsApp instead.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-col gap-5">
      <div className="flex items-start gap-3">
        <Sparkles className="mt-0.5 h-6 w-6 shrink-0 text-brand-deep" aria-hidden />
        <div>
          <h2 className="text-xl font-bold">{productLabel} is coming soon</h2>
          <p className="mt-1 text-ink-soft">
            Instant online quotes for {productLabel.toLowerCase()} aren&apos;t live yet - keep an eye out, we&apos;re adding
            it soon. You don&apos;t have to wait though: one of our agents can arrange cover with you directly, and will
            take it from here.
          </p>
        </div>
      </div>

      {highlights && highlights.length > 0 && (
        <div className="rounded-control bg-neutral px-4 py-3">
          <p className="text-sm font-semibold text-ink">What we&apos;re planning to cover</p>
          <ul className="mt-1.5 list-disc pl-5 text-sm text-ink-soft">
            {highlights.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </div>
      )}

      {sent ? (
        <div className="rounded-control bg-status-success/10 px-4 py-3 text-sm text-status-success">
          Thank you - we&apos;ve got your details. An agent will call you shortly.
        </div>
      ) : (
        <form onSubmit={requestCallback} className="grid gap-4 sm:grid-cols-2">
          <Input label="Your full name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          <Input label="Your phone number" type="tel" placeholder="07XX XXX XXX" value={phone} onChange={(e) => setPhone(e.target.value)} />
          {error && <p className="text-sm text-status-error sm:col-span-2">{error}</p>}
          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <Button type="submit" disabled={busy}>
              {busy ? "Sending…" : "Request a call from an agent"}
            </Button>
            <a
              href={`https://wa.me/${WHATSAPP_NUMBER}?text=${waText}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 text-sm font-semibold text-brand-deep hover:underline"
            >
              <MessageCircle className="h-4 w-4" aria-hidden /> Chat to an agent on WhatsApp
            </a>
          </div>
        </form>
      )}

      <a href="/insurance" className="text-sm font-semibold text-brand-deep hover:underline">
        ← Browse the insurance we can quote online today
      </a>
    </Card>
  );
}

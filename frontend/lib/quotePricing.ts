import type { NormalizedQuote, OptionalExtension } from "@/lib/types";

/**
 * The new price of a quote the instant someone ticks or unticks an add-on / excess protector, before the server
 * has answered. It repeats the server's own sums (rate_card_engine): the premium is the base plus the chosen extras;
 * each levy is its rate times that premium, rounded to the cent (halves up); a flat fee is then added.
 *
 * Money is handled as whole cents, never as floating-point numbers, so the result matches the server to the cent.
 * The rates come from the quote itself (`coverage.pricing_rules`) - they are not written here - and a quote without
 * them, or with anything unexpected in its numbers, returns null: the caller then simply waits for the server.
 * The server's total always replaces this one when it arrives.
 */

export interface LivePrice {
  premium: string;
  taxes: string;
  fees: string;
  total: string;
}

interface PricingRules {
  levy_rates: string[];
  flat_fees: string;
}

export function optionsOf(q: NormalizedQuote): OptionalExtension[] {
  const raw = (q.coverage as { optional_extensions?: unknown }).optional_extensions;
  return Array.isArray(raw) ? (raw as OptionalExtension[]) : [];
}

/** "32000.50" -> 3200050. null when it is not a plain amount with at most cents. */
function toCents(value: unknown): number | null {
  if (typeof value !== "string" && typeof value !== "number") return null;
  const m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(String(value).trim());
  if (!m) return null;
  const decimals = m[3] ?? "";
  if (decimals.length > 2 && /[1-9]/.test(decimals.slice(2))) return null; // finer than cents: do not guess
  const cents = Number(m[2]) * 100 + Number(decimals.padEnd(2, "0").slice(0, 2));
  return m[1] ? -cents : cents;
}

function fromCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

/** cents * rate, rounded to the nearest cent with halves going up - exact integer arithmetic. "0.0025" -> 25 / 10000. */
function levyCents(cents: number, rate: string): number | null {
  const m = /^(\d+)(?:\.(\d+))?$/.exec(String(rate).trim());
  if (!m) return null;
  const numerator = Number(`${m[1]}${m[2] ?? ""}`);
  const denominator = 10 ** (m[2] ?? "").length;
  const a = 2 * cents * numerator + denominator;
  const b = 2 * denominator;
  return (a - (a % b)) / b;
}

export function rulesOf(q: NormalizedQuote): PricingRules | null {
  const rules = (q.coverage as { pricing_rules?: Partial<PricingRules> }).pricing_rules;
  return rules && Array.isArray(rules.levy_rates) && typeof rules.flat_fees === "string" ? (rules as PricingRules) : null;
}

/** Does this quote's own set of priced options differ from what is ticked? Only options the quote itself offers count. */
export function differsFromPriced(q: NormalizedQuote, picked: ReadonlySet<string>): boolean {
  return optionsOf(q).some((o) => o.selected !== picked.has(o.code));
}

export function livePrice(q: NormalizedQuote, picked: ReadonlySet<string>): LivePrice | null {
  const rules = rulesOf(q);
  if (!rules) return null;

  let premium = toCents(q.premium);
  if (premium === null) return null;
  for (const o of optionsOf(q)) {
    const amount = toCents(o.amount);
    if (amount === null) return null;
    if (o.selected) premium -= amount; // back out what the server already included...
    if (picked.has(o.code)) premium += amount; // ...and add what is ticked now
  }
  if (premium < 0) return null;

  let taxes = 0;
  for (const rate of rules.levy_rates) {
    const levy = levyCents(premium, rate);
    if (levy === null) return null;
    taxes += levy;
  }
  const fees = toCents(rules.flat_fees);
  if (fees === null) return null;

  return { premium: fromCents(premium), taxes: fromCents(taxes), fees: fromCents(fees), total: fromCents(premium + taxes + fees) };
}

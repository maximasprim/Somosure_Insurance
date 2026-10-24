import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import clsx from "clsx";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { ExcessLine, NormalizedQuote, OptionalExtension } from "@/lib/types";

function formatKES(amount: string) {
  return `KES ${Number(amount).toLocaleString("en-KE", { maximumFractionDigits: 0 })}`;
}

/** What each add-on code was already priced in, across every quote on screen. */
function pricedCodes(quotes: NormalizedQuote[]): Set<string> {
  const codes = new Set<string>();
  for (const q of quotes) {
    for (const o of optionsOf(q)) if (o.selected) codes.add(o.code);
  }
  return codes;
}

function optionsOf(q: NormalizedQuote): OptionalExtension[] {
  const raw = (q.coverage as { optional_extensions?: unknown }).optional_extensions;
  return Array.isArray(raw) ? (raw as OptionalExtension[]) : [];
}

function excessesOf(q: NormalizedQuote): ExcessLine[] {
  const raw = (q.deductibles as { excesses?: unknown }).excesses;
  return Array.isArray(raw) ? (raw as ExcessLine[]).filter((e) => e && typeof e.label === "string") : [];
}

/** A text field from the quote, only when it really is a non-empty string. */
function textOf(source: unknown, key: string): string | null {
  const value = (source as Record<string, unknown> | null | undefined)?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

// The engine adds this line for an add-on a particular insurer does not sell. The customise panel only
// offers what each insurer sells, so repeating it on every other card would just be noise.
const SKIPPED_EXTENSION = /^Requested extension '[^']*' is not configured for this provider - skipped\.\s*/;

/** One "label ... value" line. The value drops under the label when it is too long to sit beside it,
 *  and long words break, so nothing can push past the edge of the card on a narrow screen. */
function Line({ label, value }: { label: string; value?: string | null }) {
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 py-1.5">
      <span className="min-w-0 grow basis-40 break-words text-ink">{label}</span>
      {value ? <span className="ml-auto min-w-0 max-w-full break-words text-right text-ink-soft">{value}</span> : null}
    </li>
  );
}

/** A collapsible section with a divider above it and a chevron that turns when open. */
function Section({ title, count, children }: { title: string; count?: number; children: ReactNode }) {
  return (
    <details className="group border-t border-neutral-border py-3">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold text-ink [&::-webkit-details-marker]:hidden">
        <span className="min-w-0">
          {title}
          {count ? <span className="ml-1.5 font-normal text-ink-soft">({count})</span> : null}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-ink-soft transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="mt-2 text-sm">{children}</div>
    </details>
  );
}

export function QuoteComparison({
  quotes,
  note,
  onSelect,
  onCustomise,
  busy = false,
}: {
  quotes: NormalizedQuote[];
  note: string | null;
  onSelect: (quote: NormalizedQuote) => void;
  /** When given, each quote shows its add-ons and excess protectors as tick boxes; ticking one re-prices with the chosen codes. */
  onCustomise?: (extensions: string[]) => void;
  busy?: boolean;
}) {
  const applied = pricedCodes(quotes);
  const [picked, setPicked] = useState<Set<string>>(applied);
  // New prices came back (or a different set of quotes): the boxes follow what was actually priced.
  useEffect(() => {
    setPicked(pricedCodes(quotes));
  }, [quotes]);
  // Ticking a box re-prices straight away. A short pause lets several quick ticks go out as ONE request.
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    []
  );
  function toggle(code: string) {
    const next = new Set(picked);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    setPicked(next);
    if (!onCustomise) return;
    if (timer.current) clearTimeout(timer.current);
    const unchanged = next.size === applied.size && [...next].every((c) => applied.has(c));
    if (unchanged) return;
    timer.current = setTimeout(() => onCustomise([...next]), 300);
  }

  if (quotes.length === 0) {
    return (
      <Card className="text-center text-ink-soft">
        We couldn't reach any insurers just now. Your request was saved - we'll follow up shortly.
      </Card>
    );
  }

  const cheapest = quotes.reduce((min, q) => (Number(q.total) < Number(min.total) ? q : min), quotes[0]);

  return (
    <div className="flex min-w-0 flex-col gap-4">
      {note && <div className="rounded-control bg-brand-tint px-4 py-3 text-sm text-ink">{note}</div>}
      {onCustomise && busy && (
        <div
          className="rounded-control border border-brand/60 bg-brand-tint/60 px-4 py-2 text-sm text-ink"
          role="status"
        >
          Updating your prices…
        </div>
      )}
      <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
        {quotes.map((q) => {
          const options = onCustomise ? optionsOf(q) : [];
          const protectors = options.filter((o) => o.kind === "excess_protector");
          const extras = options.filter((o) => o.kind !== "excess_protector");
          const excesses = excessesOf(q);
          const freeBenefits = q.coverage.free_benefits ?? [];
          const includedExtras =
            (q.coverage as { extensions?: { code: string; label: string; amount: string; limit_label?: string }[] })
              .extensions ?? [];
          const notes = (q.coverage.assumptions ?? []).map((a) => a.replace(SKIPPED_EXTENSION, "").trim()).filter(Boolean);
          const summary = textOf(q.coverage, "summary");
          const confidenceNotice = textOf(q.coverage, "data_confidence_notice");
          const singleExcess = textOf(q.deductibles, "excess");
          const hasOptions = protectors.length > 0 || extras.length > 0;
          // Nothing to show about excess or included benefits: say so plainly instead of leaving a gap.
          const detailsMissing = !q.is_mock && freeBenefits.length === 0 && excesses.length === 0 && !singleExcess;

          const optionGroups = [
            { title: "Excess protection", hint: "Pay a little more, pay less when you claim", items: protectors },
            { title: "Extra benefits", hint: null, items: extras },
          ].filter((group) => group.items.length > 0);

          return (
            <Card key={q.id} className="flex min-w-0 flex-col gap-4 !p-4 sm:!p-6">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="break-words font-display text-lg font-bold">{q.provider_name}</h3>
                  {summary && <p className="mt-0.5 break-words text-xs text-ink-soft">{summary}</p>}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {q.id === cheapest.id && <Badge tone="success">Best price</Badge>}
                  {q.underlying_provider_name && <Badge tone="brand">Via marketplace partner</Badge>}
                  {q.is_mock && <Badge tone="neutral">Demo quote</Badge>}
                </div>
              </div>

              <div>
                <p className="font-display text-3xl font-extrabold text-ink">{formatKES(q.total)}</p>
                <p className="mt-0.5 text-xs text-ink-soft">
                  Premium {formatKES(q.premium)} · Taxes {formatKES(q.taxes)} · Fees {formatKES(q.fees)}
                </p>
                {singleExcess && <p className="mt-1.5 text-sm text-ink-soft">Excess: {singleExcess}</p>}
              </div>

              {confidenceNotice && (
                <p className="rounded-control bg-brand-tint px-3 py-2 text-xs text-ink-soft">{confidenceNotice}</p>
              )}
              {notes.length > 0 && (
                <p className="rounded-control bg-amber-50 px-3 py-2 text-xs text-amber-800">{notes.join(" ")}</p>
              )}

              {/* Add-ons already priced in, for a quote that is not offering tick boxes (e.g. a resumed quote). */}
              {!hasOptions && includedExtras.length > 0 && (
                <div className="border-t border-neutral-border pt-3 text-sm">
                  <p className="font-semibold text-ink">Extras included in this price</p>
                  <ul className="mt-1 divide-y divide-neutral-border">
                    {includedExtras.map((ext) => (
                      <Line
                        key={ext.code}
                        label={ext.limit_label ? `${ext.label} (${ext.limit_label})` : ext.label}
                        value={`+ ${formatKES(ext.amount)}`}
                      />
                    ))}
                  </ul>
                </div>
              )}

              {hasOptions && (
                <div className="border-t border-neutral-border pt-1">
                  <p className="text-sm font-semibold text-ink">Customise your cover</p>
                  {optionGroups.map((group) => (
                    <div key={group.title} className="mt-1">
                      <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">{group.title}</p>
                      {group.hint && <p className="text-xs text-ink-soft">{group.hint}</p>}
                      <ul className="mt-1 flex flex-col gap-1">
                        {group.items.map((o) => (
                          <li key={o.code}>
                            <label
                              className={clsx(
                                "flex cursor-pointer items-start gap-3 rounded-control px-2 py-2 transition-colors",
                                picked.has(o.code) ? "bg-brand-tint/60" : "hover:bg-neutral"
                              )}
                            >
                              <input
                                type="checkbox"
                                className="mt-0.5 h-5 w-5 shrink-0 cursor-pointer rounded border-neutral-border accent-brand-deep"
                                checked={picked.has(o.code)}
                                disabled={busy}
                                onChange={() => toggle(o.code)}
                              />
                              <span className="min-w-0 flex-1 break-words text-sm text-ink">
                                {o.label}
                                {o.limit_label && <span className="block text-xs text-ink-soft">{o.limit_label}</span>}
                              </span>
                              <span className="shrink-0 whitespace-nowrap text-sm font-medium text-ink">
                                + {formatKES(o.amount)}
                              </span>
                            </label>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                  <p className="mt-2 text-xs text-ink-soft">
                    Prices shown are before taxes. Your total updates as soon as you tick or untick an option.
                  </p>
                </div>
              )}

              {freeBenefits.length > 0 && (
                <Section title="Included free" count={freeBenefits.length}>
                  <ul className="divide-y divide-neutral-border">
                    {freeBenefits.map((b) => (
                      <Line key={b.code} label={b.label} value={b.limit_label ?? "Included"} />
                    ))}
                  </ul>
                </Section>
              )}

              {excesses.length > 0 && (
                <Section title="What you pay if you claim (excess)" count={excesses.length}>
                  <ul className="divide-y divide-neutral-border">
                    {excesses.map((e, i) => (
                      <Line key={`${e.peril ?? "excess"}-${i}`} label={e.label} />
                    ))}
                  </ul>
                  {protectors.length > 0 && (
                    <p className="mt-2 text-xs text-ink-soft">
                      Want to avoid these? Tick an excess protector under &ldquo;Customise your cover&rdquo;.
                    </p>
                  )}
                </Section>
              )}

              {detailsMissing && (
                <p className="border-t border-neutral-border pt-3 text-xs text-ink-soft">
                  Excess and included-benefit details for this insurer aren&rsquo;t listed here yet. Ask our team and
                  we&rsquo;ll share them before you decide.
                </p>
              )}

              <div className="mt-1 flex flex-col gap-2">
                {q.payment_options.plans && q.payment_options.plans.length > 1 && (
                  <p className="text-xs text-status-info">
                    {q.payment_options.plans.length} ways to pay, including instalments. You choose on the next step.
                  </p>
                )}
                <Button onClick={() => onSelect(q)} disabled={busy} className="w-full">
                  Continue with this quote
                </Button>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
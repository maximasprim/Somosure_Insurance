import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import {
  formatAnswer,
  formatDate,
  formatMoney,
  optionLabel,
  readQuoteSections,
  sumExtensions,
  titleCase,
} from "@/lib/applicationDisplay";
import type { ApplicationQuote } from "@/lib/types";

function Row({ label, children, strong }: { label: string; children: React.ReactNode; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt className="shrink-0 text-sm text-ink-soft">{label}</dt>
      <dd className={`min-w-0 break-words text-right text-sm ${strong ? "font-semibold text-ink" : "font-medium text-ink"}`}>
        {children}
      </dd>
    </div>
  );
}

function Heading({ children, count }: { children: React.ReactNode; count?: number }) {
  return (
    <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink-soft">
      {children}
      {count !== undefined && <span className="ml-1.5 font-normal normal-case tracking-normal">({count})</span>}
    </h3>
  );
}

export function QuoteCoverageCard({
  quote,
  details,
}: {
  quote: ApplicationQuote;
  /** The application's applicant details - read for what the customer asked for (cover type, extensions...). */
  details: Record<string, unknown>;
}) {
  const s = readQuoteSections(quote.coverage, quote.exclusions, quote.deductibles);
  const meta = quote.provider_metadata ?? {};
  const basis = typeof meta.quote_basis === "string" ? meta.quote_basis : null;
  const source = typeof meta.source_document === "string" ? meta.source_document : null;
  const unverified = typeof meta.data_confidence === "string" && meta.data_confidence !== "verified";

  const category = quote.category ?? null;
  const coverType = details.cover_type ? formatAnswer("cover_type", details.cover_type, category) : null;

  // Money breakdown. `premium` already includes the priced extensions, so
  // split them back out to show the base premium on its own.
  const extensionsTotal = sumExtensions(s.extensions);
  const basePremium = Number(quote.premium) - extensionsTotal;

  // What the customer ticked on the form but this provider did not price.
  const pricedCodes = new Set(s.extensions.map((e) => e.code));
  const asked = (key: string) => (Array.isArray(details[key]) ? (details[key] as unknown[]).map(String) : []);
  const notPriced = asked("extensions").filter((code) => !pricedCodes.has(code));
  const coverOptions = asked("cover_options");

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Quote &amp; coverage</h2>
          <p className="mt-1 text-xs text-ink-soft">
            {quote.provider_name}
            {quote.underlying_provider_name ? ` (via ${quote.underlying_provider_name})` : ""}
            {quote.valid_until ? ` · valid until ${formatDate(quote.valid_until)}` : ""}
          </p>
        </div>
        <div className="flex gap-2">
          {quote.is_mock ? (
            <Badge tone="neutral">Demo quote</Badge>
          ) : basis === "published_rate_card" ? (
            <Badge tone="success">Published rate card</Badge>
          ) : null}
        </div>
      </div>

      {/* Headline total */}
      <div className="mt-5 rounded-control bg-neutral px-5 py-4">
        <p className="text-xs uppercase tracking-wide text-ink-soft">Total payable</p>
        <p className="mt-0.5 text-2xl font-bold text-ink">{formatMoney(quote.total, quote.currency)}</p>
      </div>

      {/* The plan */}
      <dl className="mt-5 grid grid-cols-1 gap-x-10 md:grid-cols-2">
        <div className="border-b border-neutral-border/60">
          <Row label="Product">{quote.product_name ?? "-"}</Row>
        </div>
        <div className="border-b border-neutral-border/60">
          <Row label="Category">{category ? titleCase(category) : "-"}</Row>
        </div>
        {coverType && (
          <div className="border-b border-neutral-border/60">
            <Row label="Cover type">{coverType}</Row>
          </div>
        )}
        {quote.request_reference && (
          <div className="border-b border-neutral-border/60">
            <Row label="Quote reference">{quote.request_reference}</Row>
          </div>
        )}
      </dl>

      {(unverified || s.notice) && (
        <p className="mt-4 rounded-control bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {s.notice ?? "This rate has not been verified against the insurer's original rate card."}
        </p>
      )}

      {/* Premium breakdown */}
      <div className="mt-6">
        <Heading>Premium breakdown</Heading>
        <dl className="mt-1 divide-y divide-neutral-border/60">
          {extensionsTotal > 0 ? (
            <>
              <Row label="Base premium">{formatMoney(basePremium, quote.currency)}</Row>
              <Row label="Extensions">{formatMoney(extensionsTotal, quote.currency)}</Row>
            </>
          ) : (
            <Row label="Premium">{formatMoney(quote.premium, quote.currency)}</Row>
          )}
          <Row label="Taxes & levies">{formatMoney(quote.taxes, quote.currency)}</Row>
          <Row label="Fees (stamp duty)">{formatMoney(quote.fees, quote.currency)}</Row>
          <Row label="Total" strong>
            {formatMoney(quote.total, quote.currency)}
          </Row>
        </dl>
      </div>

      {/* Extensions */}
      {(s.extensions.length > 0 || notPriced.length > 0 || coverOptions.length > 0) && (
        <div className="mt-6">
          <Heading count={s.extensions.length || undefined}>
            {category === "motor" || s.extensions.length > 0 ? "Extensions" : "Cover requested"}
          </Heading>
          {s.extensions.length > 0 && (
            <ul className="mt-1 divide-y divide-neutral-border/60">
              {s.extensions.map((ext) => (
                <li key={ext.code} className="flex items-baseline justify-between gap-4 py-2">
                  <span className="min-w-0 text-sm text-ink">
                    {ext.label}
                    {ext.limit_label && <span className="ml-2 text-xs text-ink-soft">{ext.limit_label}</span>}
                  </span>
                  <span className="shrink-0 text-sm font-medium text-ink">+{formatMoney(ext.amount, quote.currency)}</span>
                </li>
              ))}
            </ul>
          )}
          {coverOptions.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {coverOptions.map((code) => (
                <Badge key={code} tone="neutral">
                  {optionLabel(category, "cover_options", code) ?? titleCase(code)}
                </Badge>
              ))}
            </div>
          )}
          {notPriced.length > 0 && (
            <p className="mt-2 text-xs text-ink-soft">
              Asked for but not priced by this provider: {notPriced.map((c) => titleCase(c)).join(", ")}.
            </p>
          )}
        </div>
      )}

      {/* Included benefits */}
      {s.freeBenefits.length > 0 && (
        <details className="group mt-6">
          <summary className="cursor-pointer list-none">
            <Heading count={s.freeBenefits.length}>Included at no extra cost</Heading>
          </summary>
          <ul className="mt-1 divide-y divide-neutral-border/60">
            {s.freeBenefits.map((b) => (
              <li key={b.code} className="flex items-baseline justify-between gap-4 py-2">
                <span className="min-w-0 text-sm text-ink">
                  {b.label}
                  {b.top_up_note && <span className="block text-xs text-ink-soft">{b.top_up_note}</span>}
                </span>
                <span className="shrink-0 text-right text-sm text-ink-soft">{b.limit_label ?? "Included"}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Excess */}
      {s.excesses.length > 0 && (
        <div className="mt-6">
          <Heading>Excess</Heading>
          <ul className="mt-1 divide-y divide-neutral-border/60">
            {s.excesses.map((e, i) => (
              <li key={`${e.peril ?? "excess"}-${i}`} className="flex items-baseline justify-between gap-4 py-2">
                <span className="text-sm text-ink-soft">{e.peril ? titleCase(e.peril) : "Excess"}</span>
                <span className="min-w-0 text-right text-sm font-medium text-ink">{e.label}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Exclusions */}
      {s.exclusionItems.length > 0 && (
        <div className="mt-6">
          <Heading>Exclusions</Heading>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {s.exclusionItems.map((item) => (
              <li key={item} className="rounded-full border border-neutral-border px-2.5 py-1 text-xs text-ink-soft">
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Anything else the provider returned */}
      {s.otherCoverage.length > 0 && (
        <div className="mt-6">
          <Heading>Other cover details</Heading>
          <dl className="mt-1 divide-y divide-neutral-border/60">
            {s.otherCoverage.map((r) => (
              <Row key={r.key} label={r.label}>
                {r.value}
              </Row>
            ))}
          </dl>
        </div>
      )}

      {/* Notes */}
      {s.assumptions.length > 0 && (
        <div className="mt-6 rounded-control bg-amber-50 px-3 py-2">
          <p className="text-xs font-semibold text-amber-900">Notes on this quote</p>
          <ul className="mt-1 list-disc pl-4 text-xs text-amber-800">
            {s.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      {source && <p className="mt-5 text-xs text-ink-soft">Priced from: {source}</p>}
    </Card>
  );
}

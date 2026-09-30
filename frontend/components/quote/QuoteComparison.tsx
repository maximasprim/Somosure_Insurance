import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { NormalizedQuote } from "@/lib/types";

function formatKES(amount: string) {
  return `KES ${Number(amount).toLocaleString("en-KE", { maximumFractionDigits: 0 })}`;
}

export function QuoteComparison({
  quotes,
  note,
  onSelect,
}: {
  quotes: NormalizedQuote[];
  note: string | null;
  onSelect: (quote: NormalizedQuote) => void;
}) {
  if (quotes.length === 0) {
    return (
      <Card className="text-center text-ink-soft">
        We couldn't reach any insurers just now. Your request was saved - we'll follow up shortly.
      </Card>
    );
  }

  const cheapest = quotes.reduce((min, q) => (Number(q.total) < Number(min.total) ? q : min), quotes[0]);

  return (
    <div className="flex flex-col gap-4">
      {note && (
        <div className="rounded-control bg-brand-tint px-4 py-3 text-sm text-ink">{note}</div>
      )}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {quotes.map((q) => (
          <Card key={q.id} className="flex flex-col gap-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-display text-lg font-bold">{q.provider_name}</h3>
                <div className="mt-1 flex gap-2">
                  {q.id === cheapest.id && <Badge tone="success">Best price</Badge>}
                  {q.underlying_provider_name && <Badge tone="brand">Via marketplace partner</Badge>}
                </div>
              </div>
              {q.is_mock && <Badge tone="neutral">Demo quote</Badge>}
            </div>

            {"data_confidence_notice" in q.coverage && (
              <p className="rounded-control bg-brand-tint px-3 py-2 text-xs text-ink-soft">
                {String((q.coverage as { data_confidence_notice?: string }).data_confidence_notice)}
              </p>
            )}

            {q.coverage.assumptions && q.coverage.assumptions.length > 0 && (
              <p className="rounded-control bg-amber-50 px-3 py-2 text-xs text-amber-800">{q.coverage.assumptions.join(" ")}</p>
            )}

            <div>
              <p className="text-3xl font-extrabold text-ink">{formatKES(q.total)}</p>
              <p className="text-xs text-ink-soft">
                Premium {formatKES(q.premium)} + taxes {formatKES(q.taxes)} + fees {formatKES(q.fees)}
              </p>
            </div>

            <ul className="flex flex-col gap-1 text-sm text-ink-soft">
              {"summary" in q.coverage && <li>{String((q.coverage as { summary?: string }).summary)}</li>}
              {"excess" in q.deductibles && <li>Excess: {String((q.deductibles as { excess?: string }).excess)}</li>}
            </ul>

            {Array.isArray((q.coverage as { extensions?: unknown[] }).extensions) &&
              ((q.coverage as { extensions?: { code: string; label: string; amount: string; limit_label?: string }[] })
                .extensions?.length ?? 0) > 0 && (
                <div className="rounded-control border border-neutral-border px-3 py-2">
                  <p className="text-xs font-semibold text-ink">Extra benefits included in this price</p>
                  <ul className="mt-1 flex flex-col gap-0.5 text-xs text-ink-soft">
                    {(
                      q.coverage as { extensions: { code: string; label: string; amount: string; limit_label?: string }[] }
                    ).extensions.map((ext) => (
                      <li key={ext.code} className="flex justify-between gap-2">
                        <span>
                          {ext.label}
                          {ext.limit_label ? ` (${ext.limit_label})` : ""}
                        </span>
                        <span className="shrink-0 font-medium text-ink">+{formatKES(ext.amount)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

            {q.coverage.free_benefits && q.coverage.free_benefits.length > 0 && (
              <details className="rounded-control border border-neutral-border px-3 py-2 text-xs text-ink-soft">
                <summary className="cursor-pointer font-semibold text-ink">
                  What's already included, free ({q.coverage.free_benefits.length})
                </summary>
                <ul className="mt-2 flex flex-col gap-1">
                  {q.coverage.free_benefits.map((b) => (
                    <li key={b.code} className="flex justify-between gap-2">
                      <span>{b.label}</span>
                      <span className="shrink-0 text-right text-ink-soft">{b.limit_label ?? "Included"}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {q.payment_options.plans && q.payment_options.plans.length > 1 && (
              <p className="text-xs text-status-info">
                {q.payment_options.plans.length} ways to pay available, including instalments - choose one on the
                next step.
              </p>
            )}

            <Button onClick={() => onSelect(q)} className="mt-auto">
              Continue with this quote
            </Button>
          </Card>
        ))}
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { EligibilityResult, FinancingApplicationResult } from "@/lib/types";

const TERM_OPTIONS = [3, 6, 10];

function formatKES(amount: string) {
  return `KES ${Number(amount).toLocaleString("en-KE", { maximumFractionDigits: 0 })}`;
}

export function FinancingOption({
  customerId,
  quoteId,
  onApplied,
}: {
  customerId: string;
  quoteId: string;
  onApplied: (application: FinancingApplicationResult) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [term, setTerm] = useState(6);
  const [eligibility, setEligibility] = useState<EligibilityResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function checkTerm(newTerm: number) {
    setTerm(newTerm);
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<EligibilityResult>("/api/v1/financing/eligibility", {
        customer_id: customerId,
        quote_id: quoteId,
        term_months: newTerm,
      });
      setEligibility(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not check financing eligibility");
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    setBusy(true);
    setError(null);
    try {
      const application = await api.post<FinancingApplicationResult>("/api/v1/financing/applications", {
        customer_id: customerId,
        quote_id: quoteId,
        term_months: term,
      });
      onApplied(application);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Financing application failed");
    } finally {
      setBusy(false);
    }
  }

  if (!expanded) {
    return (
      <button
        onClick={() => {
          setExpanded(true);
          checkTerm(term);
        }}
        className="text-sm font-semibold text-brand-deep hover:underline"
      >
        Can't pay it all at once? Spread the cost with Bidii Credit financing →
      </button>
    );
  }

  return (
    <Card className="flex flex-col gap-4 border-brand-deep/30">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Finance this premium with Bidii Credit</h3>
        {eligibility?.is_mock && <Badge tone="neutral">Demo eligibility check</Badge>}
      </div>

      <div className="flex gap-2">
        {TERM_OPTIONS.map((t) => (
          <button
            key={t}
            onClick={() => checkTerm(t)}
            className={`rounded-control border px-3 py-1.5 text-sm ${
              term === t ? "border-brand-deep bg-brand-tint font-semibold" : "border-neutral-border text-ink-soft"
            }`}
          >
            {t} months
          </button>
        ))}
      </div>

      {eligibility && eligibility.eligible && (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-ink-soft">Deposit now ({eligibility.deposit_percentage}%)</p>
            <p className="font-semibold">{formatKES(eligibility.deposit_amount)}</p>
          </div>
          <div>
            <p className="text-ink-soft">Financed amount</p>
            <p className="font-semibold">{formatKES(eligibility.financed_amount)}</p>
          </div>
          <div className="col-span-2">
            <p className="text-ink-soft">Then {term} monthly installments of</p>
            <p className="font-semibold">{formatKES(eligibility.monthly_installment ?? "0")}/month</p>
          </div>
        </div>
      )}

      {eligibility && !eligibility.eligible && (
        <p className="text-sm text-status-error">{eligibility.reason}</p>
      )}

      {error && <p className="text-sm text-status-error">{error}</p>}

      <Button onClick={apply} disabled={busy || !eligibility?.eligible}>
        {busy ? "Submitting…" : "Apply for financing"}
      </Button>

      <p className="text-xs text-ink-soft">
        This is a separate credit agreement with Bidii Credit - it does not change your insurance policy terms.
      </p>
    </Card>
  );
}

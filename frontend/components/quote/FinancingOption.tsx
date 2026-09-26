"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { EligibilityResult, FinancingApplicationResult } from "@/lib/types";

// Loan term must be 4-10 months - mirrors the FinancingSettings default
// range (admin-editable, so the actual live bounds may differ; the
// eligibility check on the backend is still the source of truth).
const TERM_OPTIONS = [4, 6, 10];

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
  const [hasExistingLogbookLoan, setHasExistingLogbookLoan] = useState(false);
  const [loanAgeMonths, setLoanAgeMonths] = useState("");
  const [isCorporate, setIsCorporate] = useState(false);
  const [eligibility, setEligibility] = useState<EligibilityResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function parsedLoanAge(value = loanAgeMonths): number | undefined {
    const n = Number(value);
    return value.trim() !== "" && Number.isFinite(n) ? n : undefined;
  }

  async function checkEligibility(newTerm = term, existingLoan = hasExistingLogbookLoan, loanAge = parsedLoanAge()) {
    setTerm(newTerm);
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<EligibilityResult>("/api/v1/financing/eligibility", {
        customer_id: customerId,
        quote_id: quoteId,
        term_months: newTerm,
        has_existing_logbook_loan: existingLoan,
        logbook_loan_age_months: existingLoan ? loanAge : undefined,
      });
      setEligibility(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not check financing eligibility");
    } finally {
      setBusy(false);
    }
  }

  function toggleExistingLoan() {
    const next = !hasExistingLogbookLoan;
    setHasExistingLogbookLoan(next);
    checkEligibility(term, next, next ? parsedLoanAge() : undefined);
  }

  async function apply() {
    setBusy(true);
    setError(null);
    try {
      const application = await api.post<FinancingApplicationResult>("/api/v1/financing/applications", {
        customer_id: customerId,
        quote_id: quoteId,
        term_months: term,
        has_existing_logbook_loan: hasExistingLogbookLoan,
        logbook_loan_age_months: hasExistingLogbookLoan ? parsedLoanAge() : undefined,
        is_corporate: isCorporate,
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
          checkEligibility();
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
            onClick={() => checkEligibility(t)}
            className={`rounded-control border px-3 py-1.5 text-sm ${
              term === t ? "border-brand-deep bg-brand-tint font-semibold" : "border-neutral-border text-ink-soft"
            }`}
          >
            {t} months
          </button>
        ))}
      </div>

      <div>
        <label className="flex items-center gap-2 text-sm text-ink-soft">
          <input
            type="checkbox"
            checked={hasExistingLogbookLoan}
            onChange={toggleExistingLoan}
            className="h-4 w-4 rounded border-neutral-border"
          />
          I already have an existing logbook loan with Bidii Credit
        </label>
        {hasExistingLogbookLoan && (
          <div className="mt-2 pl-6">
            <label className="text-xs text-ink-soft" htmlFor="loan-age">
              How many months ago did you take that loan?
            </label>
            <input
              id="loan-age"
              type="number"
              min={0}
              className="mt-1 block w-32 rounded-control border border-neutral-border px-3 py-1.5 text-sm"
              value={loanAgeMonths}
              onChange={(e) => setLoanAgeMonths(e.target.value)}
              onBlur={() => checkEligibility()}
            />
            <p className="mt-1 text-xs text-ink-soft">
              Reduced deposit, rate, and fees only apply if this is recent enough - otherwise standard terms apply.
            </p>
          </div>
        )}
      </div>

      <label className="flex items-center gap-2 text-sm text-ink-soft">
        <input
          type="checkbox"
          checked={isCorporate}
          onChange={(e) => setIsCorporate(e.target.checked)}
          className="h-4 w-4 rounded border-neutral-border"
        />
        Applying as a company/corporate entity
      </label>

      {eligibility && eligibility.eligible && (
        <div className="flex flex-col gap-3 text-sm">
          {eligibility.concession_applied && <Badge tone="success">Existing customer terms applied</Badge>}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-ink-soft">
                Deposit now {Number(eligibility.deposit_percentage) > 0 ? `(${eligibility.deposit_percentage}%)` : "(waived)"}
              </p>
              <p className="font-semibold">{formatKES(eligibility.deposit_amount)}</p>
            </div>
            <div>
              <p className="text-ink-soft">Financed amount</p>
              <p className="font-semibold">{formatKES(eligibility.financed_amount)}</p>
            </div>
            <div>
              <p className="text-ink-soft">Interest rate</p>
              <p className="font-semibold">{eligibility.interest_rate_monthly}%/month</p>
            </div>
            <div>
              <p className="text-ink-soft">Total repayable</p>
              <p className="font-semibold">{formatKES(eligibility.total_repayable ?? "0")}</p>
            </div>
          </div>

          {(Number(eligibility.loan_application_fee ?? 0) > 0 ||
            Number(eligibility.life_insurance_fee ?? 0) > 0 ||
            Number(eligibility.excise_duty_amount ?? 0) > 0) && (
            <div className="rounded-control bg-neutral-tint/40 px-3 py-2 text-xs text-ink-soft">
              <p className="font-medium text-ink">Included in total repayable:</p>
              <p>Loan application fee: {formatKES(eligibility.loan_application_fee ?? "0")}</p>
              <p>Life insurance fee: {formatKES(eligibility.life_insurance_fee ?? "0")}</p>
              <p>Excise duty: {formatKES(eligibility.excise_duty_amount ?? "0")}</p>
            </div>
          )}

          <div>
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
        This is a separate credit agreement with Bidii Credit - it does not change your insurance policy terms. You'll
        need a filled application form, your {isCorporate ? "certificate of incorporation" : "national ID"}, KRA PIN,
        the vehicle logbook, and your insurance premium quote.
      </p>
    </Card>
  );
}
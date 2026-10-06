"use client";

import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { EligibilityResult, FinancingApplicationResult } from "@/lib/types";

// Loan term must be 4-10 months - mirrors the FinancingSettings default
// range (admin-editable, so the actual live bounds may differ; the
// eligibility check on the backend is still the source of truth).
const DEFAULT_TERM_OPTIONS = [4, 6, 10];

// Build the term buttons from the live admin-configured bounds when the
// eligibility response carries them (so changing the min/max term in admin
// settings is reflected here), falling back to the original options.
function termOptions(min?: number | null, max?: number | null): number[] {
  if (min == null || max == null || min > max || max - min > 11) return DEFAULT_TERM_OPTIONS;
  return Array.from({ length: max - min + 1 }, (_, i) => min + i);
}

function formatKES(amount: string) {
  return `KES ${Number(amount).toLocaleString("en-KE", { maximumFractionDigits: 0 })}`;
}

export function FinancingOption({
  customerId,
  quoteId,
  onApplied,
  startExpanded = false,
  onExpandedChange,
}: {
  customerId: string;
  quoteId: string;
  onApplied: (application: FinancingApplicationResult) => void;
  // Both optional so existing usages behave exactly as before. PaymentStep
  // uses them so choosing financing can hide the M-Pesa form straight away.
  startExpanded?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
}) {
  const [expanded, setExpanded] = useState(startExpanded);
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

  // Only the newest check may update the screen - otherwise a slow earlier
  // response (say, from before a checkbox was ticked) could land last and
  // overwrite the figures the customer is now looking at.
  const latestCheck = useRef(0);
  const ageDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function checkEligibility(
    newTerm = term,
    existingLoan = hasExistingLogbookLoan,
    loanAge = parsedLoanAge(),
    corporate = isCorporate
  ) {
    setTerm(newTerm);
    setBusy(true);
    setError(null);
    const ticket = ++latestCheck.current;
    try {
      const res = await api.post<EligibilityResult>("/api/v1/financing/eligibility", {
        customer_id: customerId,
        quote_id: quoteId,
        term_months: newTerm,
        has_existing_logbook_loan: existingLoan,
        logbook_loan_age_months: existingLoan ? loanAge : undefined,
        is_corporate: corporate,
      });
      if (ticket === latestCheck.current) setEligibility(res);
    } catch (e) {
      if (ticket === latestCheck.current) setError(e instanceof Error ? e.message : "Could not check financing eligibility");
    } finally {
      if (ticket === latestCheck.current) setBusy(false);
    }
  }

  // When opened straight into the financing view, run the first check now.
  useEffect(() => {
    if (startExpanded) checkEligibility();
    return () => {
      if (ageDebounce.current) clearTimeout(ageDebounce.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function changeLoanAge(value: string) {
    setLoanAgeMonths(value);
    // Re-price as they type (after a short pause) rather than waiting for
    // them to click away from the box.
    if (ageDebounce.current) clearTimeout(ageDebounce.current);
    ageDebounce.current = setTimeout(() => checkEligibility(term, hasExistingLogbookLoan, parsedLoanAge(value)), 450);
  }

  function changeCorporate(next: boolean) {
    setIsCorporate(next);
    // Whether the applicant is a company changes the documents asked for
    // (shown instantly below) and, if management has set company terms, the
    // deposit/rate too - so re-run the check right away with the new value.
    checkEligibility(term, hasExistingLogbookLoan, parsedLoanAge(), next);
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
          onExpandedChange?.(true);
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

      <div className="flex flex-wrap gap-2">
        {termOptions(eligibility?.min_term_months, eligibility?.max_term_months).map((t) => (
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
              onChange={(e) => changeLoanAge(e.target.value)}
            />
            <p className="mt-1 text-xs text-ink-soft">
              {loanAgeMonths.trim() === ""
                ? `Enter the number of months to see your reduced deposit, rate and fees${
                    eligibility?.concession_loan_age_max_months != null
                      ? ` - they apply to loans taken within the last ${eligibility.concession_loan_age_max_months} months`
                      : ""
                  }.`
                : eligibility?.concession_applied
                ? "Great - your existing-customer terms are applied below."
                : `Reduced terms only apply to a loan taken within the last ${
                    eligibility?.concession_loan_age_max_months ?? "few"
                  } months - standard terms apply for now.`}
            </p>
          </div>
        )}
      </div>

      <label className="flex items-center gap-2 text-sm text-ink-soft">
        <input
          type="checkbox"
          checked={isCorporate}
          onChange={(e) => changeCorporate(e.target.checked)}
          className="h-4 w-4 rounded border-neutral-border"
        />
        Applying as a company/corporate entity
      </label>
      {isCorporate && (
        <p className="-mt-2 pl-6 text-xs text-ink-soft">
          Company applications use your certificate of incorporation instead of a national ID.
        </p>
      )}

      {eligibility && eligibility.eligible && (
        <div className={`flex flex-col gap-3 text-sm transition-opacity ${busy ? "opacity-50" : "opacity-100"}`} aria-busy={busy}>
          {eligibility.corporate_terms_applied && <Badge tone="success">Company terms applied</Badge>}
          {eligibility.concession_applied && (
            <div className="flex flex-col gap-1">
              <Badge tone="success" className="self-start">Existing customer terms applied</Badge>
              {eligibility.standard_interest_rate_monthly && eligibility.standard_deposit_percentage && (
                <p className="text-xs text-ink-soft">
                  Instead of the standard {eligibility.standard_deposit_percentage}% deposit and{" "}
                  {eligibility.standard_interest_rate_monthly}%/month interest.
                </p>
              )}
            </div>
          )}
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
        {busy ? "Working…" : "Apply for financing"}
      </Button>
      {eligibility?.eligible && (
        <p className="-mt-2 text-xs text-ink-soft">
          {Number(eligibility.deposit_amount) > 0
            ? `You'll pay the ${formatKES(eligibility.deposit_amount)} deposit by M-Pesa once financing is approved.`
            : "No deposit to pay - nothing is due by M-Pesa."}
        </p>
      )}
      {onExpandedChange && (
        <button
          type="button"
          onClick={() => {
            setExpanded(false);
            onExpandedChange(false);
          }}
          className="self-start text-xs font-semibold text-brand-deep hover:underline"
        >
          ← Pay the full premium instead
        </button>
      )}

      <p className="text-xs text-ink-soft">
        This is a separate credit agreement with Bidii Credit - it does not change your insurance policy terms. You'll
        need a filled application form, your {isCorporate ? "certificate of incorporation" : "national ID"}, KRA PIN,
        the vehicle logbook, and your insurance premium quote.
      </p>
    </Card>
  );
}
"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { FinancingOption } from "@/components/quote/FinancingOption";
import { FinancingDocumentsStep } from "@/components/quote/FinancingDocumentsStep";
import { api } from "@/lib/api";
import type { FinancingApplicationResult, PaymentInitiateResult, PaymentPlanOption, PaymentStatusResult } from "@/lib/types";

function formatKES(amount: string | number) {
  return `KES ${Number(amount).toLocaleString("en-KE", { maximumFractionDigits: 0 })}`;
}

// What is charged now once a referral discount (applied by staff) is taken off.
// Mirrors the server, which does the real calculation: paying in full takes it
// off the total; a payment plan takes it off the FIRST payment, which never
// drops below KES 1.
export function dueAfterDiscount(due: number, discount: number, isInstallmentPlan: boolean): number {
  if (!(discount > 0)) return due;
  return isInstallmentPlan ? due - Math.min(discount, Math.max(due - 1, 0)) : Math.max(due - discount, 1);
}

export function PaymentStep({
  applicationId,
  customerId,
  quoteId,
  amount,
  paymentPlans,
  onPaid,
  onFinancedNoDeposit,
}: {
  applicationId: string;
  customerId: string;
  quoteId: string;
  amount: string;
  paymentPlans?: PaymentPlanOption[];
  onPaid: () => void;
  // Optional: called when financing is approved and NO deposit is due, so
  // there is nothing to pay by M-Pesa. Callers that don't pass it simply
  // get the explanatory message without a finish button.
  onFinancedNoDeposit?: () => void;
}) {
  const [phone, setPhone] = useState("");
  const [payment, setPayment] = useState<PaymentInitiateResult | null>(null);
  const [status, setStatus] = useState<PaymentStatusResult | null>(null);
  const [financing, setFinancing] = useState<FinancingApplicationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A referral discount staff may have applied to this application. When there
  // is none (the normal case) nothing below changes.
  const [discount, setDiscount] = useState(0);
  useEffect(() => {
    api
      .get<{ discount_amount: string | null }>(`/api/v1/applications/${applicationId}/discount`)
      .then((res) => setDiscount(Number(res.discount_amount ?? 0)))
      .catch(() => undefined);
  }, [applicationId]);

  // A plan other than "pay in full" and financing (Bidii Credit) are two
  // different ways of spreading the same premium out - offering both at
  // once would double-count what's owed, so picking one hides the other.
  const plans = paymentPlans ?? [];
  const hasChoice = plans.length > 1;
  const [selectedOption, setSelectedOption] = useState<PaymentPlanOption | null>(
    paymentPlans?.find((p) => p.type === "full") ?? paymentPlans?.[0] ?? null
  );

  const financingApproved = financing?.status === "approved";

  // True while the customer has the financing panel open. Choosing
  // financing replaces "pay by M-Pesa now": the M-Pesa form and the
  // pay-in-instalments options step aside until financing is approved
  // (and then only if a deposit is actually due).
  const [financeMode, setFinanceMode] = useState(false);
  const noDepositFinanced = financingApproved && financing !== null && Number(financing.deposit_amount) === 0;
  const showMpesaForm = !payment && !noDepositFinanced && (!financeMode || financing !== null);

  // Once financing is approved, only the deposit is collected via M-Pesa now
  // - the remainder is a separate Bidii Credit installment schedule, never
  // altering the insurance premium itself (spec §14). If Bidii Credit
  // rejected it, the full premium is still due here as normal.
  const dueNowFor = (opt: PaymentPlanOption) => dueAfterDiscount(Number(opt.due_now), discount, opt.type !== "full");
  const amountDue =
    financingApproved && financing
      ? financing.deposit_amount
      : String(
          dueAfterDiscount(Number(selectedOption?.due_now ?? amount), discount, !!selectedOption && selectedOption.type !== "full")
        );

  async function handleInitiate() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<PaymentInitiateResult>("/api/v1/payments/initiate", {
        application_id: applicationId,
        customer_id: customerId,
        amount: amountDue,
        phone,
        method: "mpesa",
        plan_code: !financingApproved && selectedOption && selectedOption.type !== "full" ? selectedOption.plan_code : undefined,
        installments: !financingApproved && selectedOption && selectedOption.type !== "full" ? selectedOption.installments : undefined,
      });
      setPayment(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start payment - has this application been approved yet?");
    } finally {
      setBusy(false);
    }
  }

  async function handleNextInstallment() {
    if (!payment) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<PaymentInitiateResult>(`/api/v1/payments/${payment.payment_id}/next-installment`, { phone });
      setPayment(res);
      setStatus(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the next instalment");
    } finally {
      setBusy(false);
    }
  }

  async function pollStatus(paymentId: string) {
    const res = await api.get<PaymentStatusResult>(`/api/v1/payments/${paymentId}/status`);
    setStatus(res);
    if (res.status === "successful" && !payment?.remaining_schedule?.length) onPaid();
    return res.status;
  }

  // Dev-only: stands in for the customer completing the STK push on their
  // phone. Posts a signed callback through the real webhook verification
  // path - see backend app/api/v1/payments.py.
  async function handleSimulate(outcome: "successful" | "failed") {
    if (!payment) return;
    setBusy(true);
    try {
      await api.post(`/api/v1/payments/${payment.provider_transaction_id}/simulate-completion?outcome=${outcome}&amount=${amountDue}`, {});
      await pollStatus(payment.payment_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setBusy(false);
    }
  }

  const remaining = status?.status === "successful" ? payment?.remaining_schedule ?? [] : [];

  return (
    <Card className="flex flex-col gap-5">
      <div>
        <h2 className="text-xl font-bold">Pay for your policy</h2>
        <p className="mt-1 text-sm text-ink-soft">
          {financingApproved && financing ? (
            <>
              Deposit due now: <span className="font-semibold text-ink">{formatKES(amountDue)}</span>
              {" "}- remaining KES {Number(financing.financed_amount).toLocaleString()} financed over{" "}
              {financing.term_months} months with Bidii Credit at {financing.interest_rate_monthly}%/month.
            </>
          ) : financeMode && !financing ? (
            <>Choose your financing terms below - nothing is due by M-Pesa until your financing is approved.</>
          ) : (
            <>Amount due now: <span className="font-semibold text-ink">{formatKES(amountDue)}</span></>
          )}
        </p>
      </div>

      {discount > 0 && !payment && (
        <div className="rounded-control bg-status-success/10 px-4 py-3 text-sm text-status-success">
          A referral discount of <span className="font-semibold">{formatKES(discount)}</span> has been applied to this policy - thank you for referring
          a friend.
        </div>
      )}

      {!payment && !financing && hasChoice && !financeMode && (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium text-ink">How would you like to pay?</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {plans.map((opt) => (
              <label
                key={`${opt.plan_code}-${opt.installments}`}
                className={`flex cursor-pointer flex-col gap-1 rounded-control border px-4 py-3 text-sm ${
                  selectedOption?.plan_code === opt.plan_code && selectedOption?.installments === opt.installments
                    ? "border-brand bg-brand-tint"
                    : "border-neutral-border"
                }`}
              >
                <span className="flex items-center gap-2 font-medium text-ink">
                  <input
                    type="radio"
                    name="payment_plan"
                    checked={selectedOption?.plan_code === opt.plan_code && selectedOption?.installments === opt.installments}
                    onChange={() => setSelectedOption(opt)}
                  />
                  {opt.label}
                </span>
                <span className="text-xs text-ink-soft">
                  {formatKES(dueNowFor(opt))} due now
                  {opt.schedule.length > 1 ? `, then ${opt.schedule.length - 1} more payment(s)` : ""}
                  {opt.sticker_months_per_payment ? ` - each payment covers ${opt.sticker_months_per_payment} month(s) of sticker` : ""}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}

      {!payment && !financing && discount === 0 && (
        <FinancingOption customerId={customerId} quoteId={quoteId} onApplied={setFinancing} onExpandedChange={setFinanceMode} />
      )}

      {financing && financingApproved && (
        <>
          <Badge tone="success">Financing approved - {financing.reference}</Badge>
          <FinancingDocumentsStep financingApplicationId={financing.id} isCorporate={financing.is_corporate} />
        </>
      )}

      {financing && !financingApproved && (
        <div className="rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">
          Bidii Credit couldn't approve financing for this application{financing.rejection_reason ? `: ${financing.rejection_reason}` : "."}{" "}
          You can still pay the full premium below.
        </div>
      )}

      {noDepositFinanced && !payment && (
        <div className="flex flex-col items-start gap-3 rounded-control bg-status-success/10 px-4 py-3 text-sm text-status-success">
          <p>
            No deposit is due - your financing covers the whole premium, so there&apos;s nothing to pay by M-Pesa now. Our
            team will confirm with Bidii Credit and activate your policy.
          </p>
          {onFinancedNoDeposit && (
            <Button onClick={onFinancedNoDeposit} size="lg">
              Finish
            </Button>
          )}
        </div>
      )}

      {showMpesaForm && (
        <>
          <Input label="M-Pesa phone number" placeholder="07XX XXX XXX" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <Button onClick={handleInitiate} disabled={busy || !phone} size="lg">
            {busy ? "Sending prompt…" : financingApproved ? `Pay ${formatKES(amountDue)} deposit with M-Pesa` : "Pay with M-Pesa"}
          </Button>
        </>
      )}

      {payment && !status && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-ink-soft">
            A payment prompt was sent to <strong>{phone}</strong>. Enter your M-Pesa PIN to complete it.
          </p>
          <Badge tone="neutral">Demo environment - use the buttons below to simulate the outcome</Badge>
          <div className="flex gap-3">
            <Button onClick={() => handleSimulate("successful")} disabled={busy}>Simulate success</Button>
            <Button variant="ghost" onClick={() => handleSimulate("failed")} disabled={busy}>Simulate failure</Button>
          </div>
        </div>
      )}

      {status && status.status === "successful" && remaining.length === 0 && (
        <div className="rounded-control bg-status-success/10 px-4 py-3 text-sm text-status-success">
          Payment confirmed. Your policy is being issued.
        </div>
      )}

      {status && status.status === "successful" && remaining.length > 0 && (
        <div className="flex flex-col gap-3 rounded-control bg-status-success/10 px-4 py-3">
          <p className="text-sm text-status-success">
            Payment {payment?.installment_sequence} confirmed - your policy is issued and active.
          </p>
          <div className="rounded-control bg-white px-3 py-2 text-sm text-ink">
            Next payment: <span className="font-semibold">{formatKES(remaining[0].amount)}</span> due{" "}
            {new Date(remaining[0].due_date).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" })}
            {remaining[0].cover_to
              ? ` (your sticker is valid until ${new Date(remaining[0].cover_to).toLocaleDateString("en-KE", { day: "numeric", month: "short" })})`
              : ""}
          </div>
          <div className="flex gap-3">
            <Button onClick={handleNextInstallment} disabled={busy}>
              {busy ? "Sending prompt…" : "Pay next instalment now"}
            </Button>
            <Button variant="ghost" onClick={onPaid}>
              I'll pay later
            </Button>
          </div>
        </div>
      )}

      {status && status.status === "failed" && (
        <div className="rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">
          Payment failed. Please try again.
        </div>
      )}

      {error && <p className="text-sm text-status-error">{error}</p>}
    </Card>
  );
}
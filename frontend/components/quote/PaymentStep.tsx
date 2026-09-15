"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { FinancingOption } from "@/components/quote/FinancingOption";
import { api } from "@/lib/api";
import type { FinancingApplicationResult, PaymentInitiateResult, PaymentStatusResult } from "@/lib/types";

export function PaymentStep({
  applicationId,
  customerId,
  quoteId,
  amount,
  onPaid,
}: {
  applicationId: string;
  customerId: string;
  quoteId: string;
  amount: string;
  onPaid: () => void;
}) {
  const [phone, setPhone] = useState("");
  const [payment, setPayment] = useState<PaymentInitiateResult | null>(null);
  const [status, setStatus] = useState<PaymentStatusResult | null>(null);
  const [financing, setFinancing] = useState<FinancingApplicationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Once financing is approved, only the deposit is collected via M-Pesa now
  // - the remainder is a separate Bidii Credit installment schedule, never
  // altering the insurance premium itself (spec §14).
  const amountDue = financing ? financing.deposit_amount : amount;

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
      });
      setPayment(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start payment - has this application been approved yet?");
    } finally {
      setBusy(false);
    }
  }

  async function pollStatus(paymentId: string) {
    const res = await api.get<PaymentStatusResult>(`/api/v1/payments/${paymentId}/status`);
    setStatus(res);
    if (res.status === "successful") onPaid();
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

  return (
    <Card className="flex flex-col gap-5">
      <div>
        <h2 className="text-xl font-bold">Pay for your policy</h2>
        <p className="mt-1 text-sm text-ink-soft">
          {financing ? (
            <>
              Deposit due now: <span className="font-semibold text-ink">KES {Number(amountDue).toLocaleString()}</span>
              {" "}- remaining KES {Number(financing.financed_amount).toLocaleString()} financed over{" "}
              {financing.term_months} months with Bidii Credit.
            </>
          ) : (
            <>Amount due: <span className="font-semibold text-ink">KES {Number(amount).toLocaleString()}</span></>
          )}
        </p>
      </div>

      {!payment && !financing && (
        <FinancingOption customerId={customerId} quoteId={quoteId} onApplied={setFinancing} />
      )}

      {financing && (
        <Badge tone="success">Financing approved - {financing.reference}</Badge>
      )}

      {!payment && (
        <>
          <Input label="M-Pesa phone number" placeholder="07XX XXX XXX" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <Button onClick={handleInitiate} disabled={busy || !phone} size="lg">
            {busy ? "Sending prompt…" : "Pay with M-Pesa"}
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

      {status && status.status === "successful" && (
        <div className="rounded-control bg-status-success/10 px-4 py-3 text-sm text-status-success">
          Payment confirmed. Your policy is being issued.
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

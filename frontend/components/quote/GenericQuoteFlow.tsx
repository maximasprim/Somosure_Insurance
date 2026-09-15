"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { QuoteFlowSteps } from "@/components/QuoteFlowSteps";
import { DynamicQuoteForm } from "@/components/quote/DynamicQuoteForm";
import { QuoteComparison } from "@/components/quote/QuoteComparison";
import { DocumentUploadStep } from "@/components/quote/DocumentUploadStep";
import { PaymentStep } from "@/components/quote/PaymentStep";
import { api, isLoggedIn } from "@/lib/api";
import type { CategoryConfig } from "@/lib/quoteFields";
import type { ApplicationResult, CustomerProfile, NormalizedQuote, QuoteRequestResult } from "@/lib/types";

// Guest quotes are genuinely anonymous until the backend resolves a real
// customer from the phone/name fields in the form answers (see
// app/services/quote_service.py's resolve_customer) - this placeholder is
// only ever used transiently before that resolution completes.
const GUEST_CUSTOMER_ID = "00000000-0000-0000-0000-000000000000";

type Step = "form" | "compare" | "documents" | "awaiting_approval" | "payment" | "done";

export function GenericQuoteFlow({ config }: { config: CategoryConfig }) {
  const [step, setStep] = useState<Step>("form");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QuoteRequestResult | null>(null);
  const [application, setApplication] = useState<ApplicationResult | null>(null);
  const [selectedQuote, setSelectedQuote] = useState<NormalizedQuote | null>(null);
  const [customerId, setCustomerId] = useState(GUEST_CUSTOMER_ID);

  useEffect(() => {
    if (isLoggedIn()) {
      api.get<CustomerProfile>("/api/v1/me").then((p) => setCustomerId(p.id)).catch(() => {});
    }
  }, []);

  async function handleFormSubmit(values: Record<string, string>) {
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post<QuoteRequestResult>("/api/v1/quotes", { category: config.category, answers: values });
      setResult(res);
      if (res.customer_id) setCustomerId(res.customer_id);
      setStep("compare");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong getting your quotes");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSelectQuote(quote: NormalizedQuote) {
    setSubmitting(true);
    setError(null);
    try {
      const app = await api.post<ApplicationResult>("/api/v1/applications", {
        quote_id: quote.id, customer_id: customerId, applicant_details: {},
      });
      setApplication(app);
      setSelectedQuote(quote);
      setStep("documents");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start your application");
    } finally {
      setSubmitting(false);
    }
  }

  const stepIndex = { form: 0, compare: 1, documents: 2, awaiting_approval: 2, payment: 2, done: 3 }[step];

  return (
    <main className="mx-auto max-w-4xl px-6 py-12 md:py-16">
      <h1 className="text-2xl font-bold md:text-3xl">{config.title}</h1>
      <p className="mt-1 text-ink-soft">Reference {result?.reference ?? "will appear once you submit"}</p>

      <div className="mt-8">
        <QuoteFlowSteps current={stepIndex} />
      </div>

      {error && <div className="mb-6 rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}

      {step === "form" && (
        <Card>
          <DynamicQuoteForm config={config} onSubmit={handleFormSubmit} submitting={submitting} />
        </Card>
      )}

      {step === "compare" && result && (
        <QuoteComparison quotes={result.quotes} note={result.note} onSelect={handleSelectQuote} />
      )}

      {step === "documents" && application && (
        <DocumentUploadStep applicationId={application.id} onSubmitted={() => setStep("awaiting_approval")} />
      )}

      {step === "awaiting_approval" && (
        <Card className="flex flex-col items-start gap-3">
          <h2 className="text-xl font-bold">Under review</h2>
          <p className="text-ink-soft">
            Your application <span className="font-semibold text-ink">{application?.reference}</span> is with our
            underwriting team. You'll be notified as soon as it's approved and ready for payment.
          </p>
          <Button onClick={() => setStep("payment")}>I've been notified it's approved - continue to payment</Button>
        </Card>
      )}

      {step === "payment" && application && selectedQuote && (
        <PaymentStep
          applicationId={application.id}
          customerId={customerId}
          quoteId={selectedQuote.id}
          amount={selectedQuote.total}
          onPaid={() => setStep("done")}
        />
      )}

      {step === "done" && (
        <Card className="flex flex-col items-start gap-3">
          <h2 className="text-xl font-bold">You're covered</h2>
          <p className="text-ink-soft">
            Application <span className="font-semibold text-ink">{application?.reference}</span> - payment received
            and your policy is being issued.
          </p>
          <Button variant="ghost" onClick={() => (window.location.href = "/")}>Back to home</Button>
        </Card>
      )}
    </main>
  );
}

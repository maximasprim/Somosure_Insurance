"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { QuoteFlowSteps } from "@/components/QuoteFlowSteps";
import { MotorQuoteForm, type MotorQuoteFormValues } from "@/components/quote/MotorQuoteForm";
import { QuoteComparison } from "@/components/quote/QuoteComparison";
import { DocumentUploadStep } from "@/components/quote/DocumentUploadStep";
import { PaymentStep } from "@/components/quote/PaymentStep";
import { api, isLoggedIn } from "@/lib/api";
import type { ApplicationResult, CustomerProfile, NormalizedQuote, QuoteRequestResult } from "@/lib/types";

// Guest quotes are genuinely anonymous until an application is created -
// the backend accepts a null customer_id for the initial quote request
// (spec §8: "continue as guest"). Turning a guest into a real Customer
// record server-side (matched by phone/email, not requiring login) is
// deferred - for now, an unauthenticated visitor uses this placeholder and
// a logged-in one uses their real customer record fetched below.
const GUEST_CUSTOMER_ID = "00000000-0000-0000-0000-000000000000";

type Step = "form" | "compare" | "documents" | "awaiting_approval" | "payment" | "done";

export default function MotorQuotePage() {
  const [step, setStep] = useState<Step>("form");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QuoteRequestResult | null>(null);
  const [application, setApplication] = useState<ApplicationResult | null>(null);
  const [selectedQuote, setSelectedQuote] = useState<NormalizedQuote | null>(null);
  const [customerId, setCustomerId] = useState(GUEST_CUSTOMER_ID);

  useEffect(() => {
    if (isLoggedIn()) {
      api
        .get<CustomerProfile>("/api/v1/me")
        .then((profile) => setCustomerId(profile.id))
        .catch(() => {
          /* fall back to guest id silently - session may be stale */
        });
    }
  }, []);

  async function handleFormSubmit(values: MotorQuoteFormValues) {
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post<QuoteRequestResult>("/api/v1/quotes", {
        category: "motor",
        answers: values,
      });
      setResult(res);
      // The backend resolves (or creates) a real guest Customer from the
      // form's owner_phone/owner_name and returns its id here - without
      // reading it back, a guest application would be created against the
      // placeholder UUID, which doesn't exist as a real Customer row and
      // would fail with a foreign-key violation at application-creation
      // time. Only keep the placeholder if resolution genuinely returned
      // nothing (shouldn't happen given the form requires a phone number).
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
        quote_id: quote.id,
        customer_id: customerId,
        applicant_details: {},
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

  const stepIndex = {
    form: 0,
    compare: 1,
    documents: 2,
    awaiting_approval: 2,
    payment: 2,
    done: 3,
  }[step];

  return (
    <main className="mx-auto max-w-7xl px-6 py-12 md:py-16">
      <h1 className="text-2xl font-bold md:text-3xl">Motor insurance quote</h1>
      <p className="mt-1 text-ink-soft">Reference {result?.reference ?? "will appear once you submit"}</p>

      <div className="mt-8">
        <QuoteFlowSteps current={stepIndex} />
      </div>

      {error && (
        <div className="mb-6 rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>
      )}

      {step === "form" && (
        <Card>
          <MotorQuoteForm onSubmit={handleFormSubmit} submitting={submitting} />
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
            underwriting team. You'll be notified as soon as it's approved and ready for payment - usually within a
            few hours.
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
            and your policy is being issued. Documents will appear in your account shortly.
          </p>
          <Button variant="ghost" onClick={() => (window.location.href = "/")}>
            Back to home
          </Button>
        </Card>
      )}
    </main>
  );
}

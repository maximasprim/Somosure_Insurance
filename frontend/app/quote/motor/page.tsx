"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { QuoteFlowSteps } from "@/components/QuoteFlowSteps";
import { MotorQuoteForm, type MotorQuoteFormValues } from "@/components/quote/MotorQuoteForm";
import { QuoteComparison } from "@/components/quote/QuoteComparison";
import { DocumentUploadStep } from "@/components/quote/DocumentUploadStep";
import { PaymentStep } from "@/components/quote/PaymentStep";
import { DocumentChecklistCard } from "@/components/quote/DocumentChecklistCard";
import { ApprovalWaitStep } from "@/components/quote/ApprovalWaitStep";
import { ResumeQuoteCard } from "@/components/quote/ResumeQuoteCard";
import { getStoredReferral } from "@/lib/referral";
import { clearQuoteSession, loadQuoteSession, saveQuoteSession, type SavedQuoteSession } from "@/lib/quoteSession";
import { api, isLoggedIn } from "@/lib/api";
import type { ApplicationResult, CustomerProfile, NormalizedQuote, QuoteRequestResult } from "@/lib/types";

// Guest quotes are genuinely anonymous until an application is created -
// the backend accepts a null customer_id for the initial quote request
// (spec §8: "continue as guest"). Turning a guest into a real Customer
// record server-side (matched by phone/email, not requiring login) is
// deferred - for now, an unauthenticated visitor uses this placeholder and
// a logged-in one uses their real customer record fetched below.
const GUEST_CUSTOMER_ID = "00000000-0000-0000-0000-000000000000";

type Step = "form" | "compare" | "documents" | "awaiting_approval" | "payment" | "financed" | "done";

export default function MotorQuotePage() {
  const [step, setStep] = useState<Step>("form");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QuoteRequestResult | null>(null);
  const [application, setApplication] = useState<ApplicationResult | null>(null);
  const [selectedQuote, setSelectedQuote] = useState<NormalizedQuote | null>(null);
  const [customerId, setCustomerId] = useState(GUEST_CUSTOMER_ID);

  // Save-and-resume (see lib/quoteSession.ts). Saved only up to "awaiting
  // approval"; reaching payment clears it so a paid customer is never
  // shown a second payment form on return.
  const [resumable, setResumable] = useState<SavedQuoteSession | null>(null);
  useEffect(() => {
    setResumable(loadQuoteSession("motor"));
  }, []);
  useEffect(() => {
    if ((step === "compare" || step === "documents" || step === "awaiting_approval") && result) {
      saveQuoteSession({ category: "motor", step, result, customerId, application, selectedQuote });
    } else if (step === "payment" || step === "financed" || step === "done") {
      clearQuoteSession("motor");
    }
  }, [step, result, customerId, application, selectedQuote]);

  function resumeSession(saved: SavedQuoteSession) {
    setResult(saved.result);
    setCustomerId(saved.customerId);
    setApplication(saved.application);
    setSelectedQuote(saved.selectedQuote);
    setStep(saved.step);
    setResumable(null);
  }
  function discardSession() {
    clearQuoteSession("motor");
    setResumable(null);
  }

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
        referral_code: getStoredReferral(),
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
    financed: 3,
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

      {step === "form" && resumable && (
        <div className="mb-6">
          <ResumeQuoteCard saved={resumable} productLabel="Motor insurance" onResume={() => resumeSession(resumable)} onDiscard={discardSession} />
        </div>
      )}

      {step === "form" && (
        <Card>
          <MotorQuoteForm onSubmit={handleFormSubmit} submitting={submitting} />
        </Card>
      )}

      {step === "compare" && result && (
        <div className="flex flex-col gap-6">
          {result.quotes.length > 0 && <DocumentChecklistCard category="motor" />}
          <QuoteComparison quotes={result.quotes} note={result.note} onSelect={handleSelectQuote} />
        </div>
      )}

      {step === "documents" && application && (
        <DocumentUploadStep applicationId={application.id} onSubmitted={() => setStep("awaiting_approval")} />
      )}

      {step === "awaiting_approval" && application && (
        <ApprovalWaitStep
          applicationId={application.id}
          reference={application.reference}
          onApproved={() => setStep("payment")}
        />
      )}

      {step === "payment" && application && selectedQuote && (
        <PaymentStep
          applicationId={application.id}
          customerId={customerId}
          quoteId={selectedQuote.id}
          amount={selectedQuote.total}
          paymentPlans={selectedQuote.payment_options.plans}
          onPaid={() => setStep("done")}
          onFinancedNoDeposit={() => setStep("financed")}
        />
      )}

      {step === "financed" && (
        <Card className="flex flex-col items-start gap-3">
          <h2 className="text-xl font-bold">Financing approved</h2>
          <p className="text-ink-soft">
            Application <span className="font-semibold text-ink">{application?.reference}</span> - your Bidii Credit financing
            covers the premium, so no deposit is due. Our team will confirm with Bidii Credit and activate your policy, and
            you&apos;ll be notified when it&apos;s live.
          </p>
          <Button variant="ghost" onClick={() => (window.location.href = "/")}>
            Back to home
          </Button>
        </Card>
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

"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { QuoteFlowSteps } from "@/components/QuoteFlowSteps";
import { DynamicQuoteForm } from "@/components/quote/DynamicQuoteForm";
import { QuoteComparison } from "@/components/quote/QuoteComparison";
import { DocumentUploadStep } from "@/components/quote/DocumentUploadStep";
import { PaymentStep } from "@/components/quote/PaymentStep";
import { DocumentChecklistCard } from "@/components/quote/DocumentChecklistCard";
import { ApprovalWaitStep } from "@/components/quote/ApprovalWaitStep";
import { ComingSoonCard, useCategoryAvailability } from "@/components/quote/ComingSoonCard";
import type { QuoteAnswers } from "@/components/quote/DynamicQuoteForm";
import { ResumeQuoteCard } from "@/components/quote/ResumeQuoteCard";
import { getStoredReferral } from "@/lib/referral";
import { clearQuoteSession, loadQuoteSession, saveQuoteSession, type SavedQuoteSession } from "@/lib/quoteSession";
import { api, isLoggedIn } from "@/lib/api";
import type { CategoryConfig } from "@/lib/quoteFields";
import type { ApplicationResult, CustomerProfile, NormalizedQuote, QuoteRequestResult } from "@/lib/types";

// Guest quotes are genuinely anonymous until the backend resolves a real
// customer from the phone/name fields in the form answers (see
// app/services/quote_service.py's resolve_customer) - this placeholder is
// only ever used transiently before that resolution completes.
const GUEST_CUSTOMER_ID = "00000000-0000-0000-0000-000000000000";

type Step = "form" | "compare" | "documents" | "awaiting_approval" | "payment" | "financed" | "done";

export function GenericQuoteFlow({ config }: { config: CategoryConfig }) {
  const [step, setStep] = useState<Step>("form");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QuoteRequestResult | null>(null);
  const [application, setApplication] = useState<ApplicationResult | null>(null);
  const [selectedQuote, setSelectedQuote] = useState<NormalizedQuote | null>(null);
  const [customerId, setCustomerId] = useState(GUEST_CUSTOMER_ID);

  // A product with no live pricing yet (e.g. medical) shows a "coming soon -
  // talk to an agent" screen instead of the quote form. Fails open, see
  // useCategoryAvailability.
  const availability = useCategoryAvailability(config.category, config.comingSoon);
  const productLabel = config.title.replace(/ quote$/i, "");

  // Save-and-resume (see lib/quoteSession.ts). Saved only up to "awaiting
  // approval"; reaching payment clears it so a paid customer is never
  // shown a second payment form on return.
  const [resumable, setResumable] = useState<SavedQuoteSession | null>(null);
  useEffect(() => {
    setResumable(loadQuoteSession(config.category));
  }, [config.category]);
  useEffect(() => {
    if ((step === "compare" || step === "documents" || step === "awaiting_approval") && result) {
      saveQuoteSession({ category: config.category, step, result, customerId, application, selectedQuote });
    } else if (step === "payment" || step === "financed" || step === "done") {
      clearQuoteSession(config.category);
    }
  }, [step, result, customerId, application, selectedQuote, config.category]);

  function resumeSession(saved: SavedQuoteSession) {
    setResult(saved.result);
    setCustomerId(saved.customerId);
    setApplication(saved.application);
    setSelectedQuote(saved.selectedQuote);
    setStep(saved.step);
    setResumable(null);
  }
  function discardSession() {
    clearQuoteSession(config.category);
    setResumable(null);
  }

  useEffect(() => {
    if (isLoggedIn()) {
      api.get<CustomerProfile>("/api/v1/me").then((p) => setCustomerId(p.id)).catch(() => {});
    }
  }, []);

  async function handleFormSubmit(values: QuoteAnswers) {
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post<QuoteRequestResult>("/api/v1/quotes", {
        category: config.category,
        answers: values,
        referral_code: getStoredReferral(),
      });
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

  const stepIndex = { form: 0, compare: 1, documents: 2, awaiting_approval: 2, payment: 2, financed: 3, done: 3 }[step];

  return (
    <main className="mx-auto max-w-4xl px-6 py-12 md:py-16">
      <h1 className="text-2xl font-bold md:text-3xl">{config.title}</h1>
      {!config.comingSoon && (
        <p className="mt-1 text-ink-soft">Reference {result?.reference ?? "will appear once you submit"}</p>
      )}

      {availability === "coming_soon" && step === "form" ? (
        <div className="mt-8">
          <ComingSoonCard category={config.category} productLabel={productLabel} highlights={config.highlights} />
        </div>
      ) : (
      <>
      <div className="mt-8">
        <QuoteFlowSteps current={stepIndex} />
      </div>

      {error && <div className="mb-6 rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}

      {step === "form" && resumable && availability !== "coming_soon" && (
        <div className="mb-6">
          <ResumeQuoteCard saved={resumable} productLabel={productLabel} onResume={() => resumeSession(resumable)} onDiscard={discardSession} />
        </div>
      )}

      {step === "form" && availability === "loading" && (
        <Card>
          <p className="text-sm text-ink-soft">Getting things ready…</p>
        </Card>
      )}

      {step === "form" && availability !== "loading" && (
        <Card>
          <DynamicQuoteForm config={config} onSubmit={handleFormSubmit} submitting={submitting} />
        </Card>
      )}

      {step === "compare" && result && (
        <div className="flex flex-col gap-6">
          {result.quotes.length > 0 && <DocumentChecklistCard category={config.category} />}
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
            and your policy is being issued.
          </p>
          <Button variant="ghost" onClick={() => (window.location.href = "/")}>Back to home</Button>
        </Card>
      )}
      </>
      )}
    </main>
  );
}

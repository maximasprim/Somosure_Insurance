"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api, getTokenRole } from "@/lib/api";
import type { FinancingApplicationDetail } from "@/lib/types";

const STATUS_TONE: Record<string, "success" | "neutral" | "error" | "brand"> = {
  eligibility_checked: "neutral",
  submitted: "brand",
  approved: "success",
  rejected: "error",
  cancelled: "neutral",
};

// Mirrors ALLOWED_STAFF_TRANSITIONS in app/services/financing_service.py -
// the backend still enforces this independently, and also gates who may
// set a custom interest rate while approving.
const NEXT_STEPS: Record<string, string[]> = {
  submitted: ["approved", "rejected"],
  rejected: ["approved"],
};

const REQUIRED_DOCS_INDIVIDUAL = ["application_form", "logbook", "national_id", "kra_pin", "premium_quote"];
const REQUIRED_DOCS_CORPORATE = ["application_form", "logbook", "certificate_of_incorporation", "kra_pin", "premium_quote"];

function formatLabel(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatKES(amount: string) {
  return `KES ${Number(amount).toLocaleString("en-KE", { maximumFractionDigits: 0 })}`;
}

export default function AdminFinancingDetailPage({ params }: { params: { id: string } }) {
  const [application, setApplication] = useState<FinancingApplicationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [rateOverride, setRateOverride] = useState("");
  const [busy, setBusy] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);
  const role = typeof window !== "undefined" ? getTokenRole() : null;
  const canSetRate = role === "management" || role === "super_admin";

  async function load() {
    try {
      setApplication(await api.get<FinancingApplicationDetail>(`/api/v1/admin/financing/applications/${params.id}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load this financing application - are you logged in as staff?");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  async function decide(toStatus: string) {
    if (!application) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/v1/admin/financing/applications/${application.id}/transition`, {
        to_status: toStatus,
        notes: notes.trim() || undefined,
        interest_rate_monthly: canSetRate && rateOverride.trim() ? rateOverride.trim() : undefined,
      });
      setNotes("");
      setRateOverride("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record that decision");
    } finally {
      setBusy(false);
    }
  }

  async function viewDocument(documentId: string) {
    if (!application) return;
    setDocError(null);
    try {
      const { url } = await api.get<{ url: string }>(
        `/api/v1/admin/financing/applications/${application.id}/documents/${documentId}/url`
      );
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setDocError(e instanceof Error ? e.message : "Could not open that document");
    }
  }

  if (error && !application) {
    return <main className="mx-auto max-w-4xl px-6 py-12 text-status-error">{error}</main>;
  }
  if (!application) {
    return <main className="mx-auto max-w-4xl px-6 py-12 text-ink-soft">Loading…</main>;
  }

  const nextSteps = NEXT_STEPS[application.status] ?? [];
  const requiredDocTypes = application.is_corporate ? REQUIRED_DOCS_CORPORATE : REQUIRED_DOCS_INDIVIDUAL;
  const uploadedTypes = new Set(application.documents.map((d) => d.document_type));

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <Link href="/admin/financing" className="text-sm text-ink-soft hover:underline">
        ← Back to financing portfolio
      </Link>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{application.reference}</h1>
          <p className="mt-1 text-xs text-ink-soft">
            Created {new Date(application.created_at).toLocaleString()} · Updated{" "}
            {new Date(application.updated_at).toLocaleString()}
          </p>
        </div>
        <Badge tone={STATUS_TONE[application.status] ?? "neutral"}>{application.status.replace(/_/g, " ")}</Badge>
      </div>

      {error && (
        <div className="mt-6 rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Card>
            <h2 className="font-semibold">Customer</h2>
            <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Full name</dt>
                <dd className="mt-0.5 text-sm text-ink">{application.customer.full_name}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Phone</dt>
                <dd className="mt-0.5 text-sm text-ink">{application.customer.phone}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Email</dt>
                <dd className="mt-0.5 text-sm text-ink">{application.customer.email ?? "-"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">National ID</dt>
                <dd className="mt-0.5 text-sm text-ink">{application.customer.id_number ?? "-"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">KRA PIN</dt>
                <dd className="mt-0.5 text-sm text-ink">{application.customer.kra_pin ?? "-"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Applicant type</dt>
                <dd className="mt-0.5 text-sm text-ink">{application.is_corporate ? "Company/corporate" : "Individual"}</dd>
              </div>
            </dl>
          </Card>

          <Card>
            <h2 className="font-semibold">Insurance quote being financed</h2>
            <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Provider</dt>
                <dd className="mt-0.5 text-sm text-ink">{application.quote.provider_name}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Product</dt>
                <dd className="mt-0.5 text-sm text-ink">{application.quote.product_name ?? "-"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Premium</dt>
                <dd className="mt-0.5 text-sm text-ink">{formatKES(application.quote.premium)}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Total</dt>
                <dd className="mt-0.5 text-sm text-ink">{formatKES(application.quote.total)}</dd>
              </div>
            </dl>
          </Card>

          <Card>
            <h2 className="font-semibold">Financing terms</h2>
            <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-3">
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">
                  Deposit {Number(application.deposit_percentage) > 0 ? `(${application.deposit_percentage}%)` : "(waived)"}
                </dt>
                <dd className="mt-0.5 text-sm text-ink">{formatKES(application.deposit_amount)}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Financed amount</dt>
                <dd className="mt-0.5 text-sm text-ink">{formatKES(application.financed_amount)}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Term</dt>
                <dd className="mt-0.5 text-sm text-ink">{application.term_months} months</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Interest rate</dt>
                <dd className="mt-0.5 text-sm text-ink">{application.interest_rate_monthly}%/month</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Total repayable</dt>
                <dd className="mt-0.5 text-sm text-ink">{formatKES(application.total_repayable)}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Existing logbook loan</dt>
                <dd className="mt-0.5 text-sm text-ink">
                  {application.has_existing_logbook_loan
                    ? `Yes${application.logbook_loan_age_months !== null ? ` (${application.logbook_loan_age_months} months old)` : ""}`
                    : "No"}
                </dd>
              </div>
            </dl>

            <div className="mt-4 flex items-center gap-2">
              <Badge tone={application.concession_applied ? "success" : "neutral"}>
                {application.concession_applied ? "Existing customer terms applied" : "Standard terms applied"}
              </Badge>
            </div>

            <div className="mt-4 rounded-control bg-neutral-tint/40 px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Fees included in total repayable</p>
              <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-3">
                <div>
                  <dt className="text-xs text-ink-soft">Loan application fee ({application.loan_application_fee_pct}%)</dt>
                  <dd className="text-sm text-ink">{formatKES(application.loan_application_fee)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-ink-soft">Life insurance fee ({application.life_insurance_fee_pct}%)</dt>
                  <dd className="text-sm text-ink">{formatKES(application.life_insurance_fee)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-ink-soft">Excise duty ({application.excise_duty_pct}%)</dt>
                  <dd className="text-sm text-ink">{formatKES(application.excise_duty_amount)}</dd>
                </div>
              </dl>
            </div>

            {application.rejection_reason && (
              <p className="mt-4 text-sm text-status-error">Rejection reason: {application.rejection_reason}</p>
            )}
          </Card>

          {application.agreement && (
            <Card>
              <h2 className="font-semibold">Installment schedule</h2>
              <div className="mt-4 flex flex-col gap-2">
                {application.agreement.installments.map((i) => (
                  <div key={i.id} className="flex items-center justify-between rounded-control border border-neutral-border px-4 py-2.5 text-sm">
                    <span>
                      #{i.installment_number} · due {new Date(i.due_date).toLocaleDateString()}
                    </span>
                    <span className="flex items-center gap-2">
                      {formatKES(i.amount)}
                      <Badge tone={i.status === "paid" ? "success" : i.status === "overdue" ? "error" : "neutral"}>{i.status}</Badge>
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Card>
            <h2 className="font-semibold">Documents</h2>
            <p className="mt-1 text-xs text-ink-soft">
              Required: {requiredDocTypes.map(formatLabel).join(", ")}
            </p>
            {docError && <p className="mt-2 text-sm text-status-error">{docError}</p>}
            <div className="mt-4 flex flex-col gap-2">
              {requiredDocTypes.map((type) => {
                const doc = application.documents.find((d) => d.document_type === type);
                return (
                  <div key={type} className="flex items-center justify-between rounded-control border border-neutral-border px-4 py-2.5">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium text-ink">{formatLabel(type)}</span>
                      <Badge tone={doc ? "success" : "error"}>{doc ? "Uploaded" : "Missing"}</Badge>
                    </div>
                    {doc && (
                      <Button variant="ghost" onClick={() => viewDocument(doc.id)}>
                        View
                      </Button>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          <Card>
            <h2 className="font-semibold">Decision</h2>
            {nextSteps.length === 0 ? (
              <p className="mt-2 text-sm text-ink-soft">
                No decision is available while this application is &quot;{application.status.replace(/_/g, " ")}&quot;.
              </p>
            ) : (
              <>
                {application.status === "rejected" && (
                  <p className="mt-1 text-xs text-ink-soft">
                    Bidii Credit auto-rejected this application. Approving here is a management-approved exception.
                  </p>
                )}
                <label className="mt-4 block text-sm font-medium text-ink" htmlFor="decision-notes">
                  Notes
                </label>
                <textarea
                  id="decision-notes"
                  className="mt-1.5 w-full rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm text-ink placeholder:text-ink-soft/60 focus:outline-none focus:ring-2 focus:ring-brand-deep/40 focus:border-brand-deep"
                  rows={4}
                  placeholder="Add context for this decision (optional, but recommended)…"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  disabled={busy}
                />
                {canSetRate && nextSteps.includes("approved") && (
                  <>
                    <label className="mt-3 block text-sm font-medium text-ink" htmlFor="rate-override">
                      Override interest rate (%/month) - optional
                    </label>
                    <input
                      id="rate-override"
                      type="number"
                      step="0.01"
                      className="mt-1.5 w-full rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm text-ink placeholder:text-ink-soft/60 focus:outline-none focus:ring-2 focus:ring-brand-deep/40 focus:border-brand-deep"
                      placeholder={`Standard is ${application.has_existing_logbook_loan ? "3.00" : "3.50"}`}
                      value={rateOverride}
                      onChange={(e) => setRateOverride(e.target.value)}
                      disabled={busy}
                    />
                  </>
                )}
                <div className="mt-3 flex flex-col gap-2">
                  {nextSteps.map((step) => (
                    <Button
                      key={step}
                      variant={step === "rejected" ? "ghost" : "primary"}
                      disabled={busy}
                      onClick={() => decide(step)}
                    >
                      {step === "approved" ? "Approve financing" : "Decline financing"}
                    </Button>
                  ))}
                </div>
              </>
            )}
          </Card>

          <Card>
            <h2 className="font-semibold">History</h2>
            <div className="mt-4 flex flex-col gap-3">
              {application.events.map((event) => (
                <div key={event.id} className="border-l-2 border-neutral-border pl-3">
                  <p className="text-sm text-ink">
                    {event.from_status ? `${event.from_status.replace(/_/g, " ")} → ` : ""}
                    {event.to_status ? event.to_status.replace(/_/g, " ") : event.event_type}
                  </p>
                  {event.notes && <p className="mt-0.5 text-sm text-ink-soft">&quot;{event.notes}&quot;</p>}
                  <p className="mt-0.5 text-xs text-ink-soft">{new Date(event.created_at).toLocaleString()}</p>
                </div>
              ))}
              {application.events.length === 0 && <p className="text-sm text-ink-soft">No activity yet.</p>}
            </div>
          </Card>
        </div>
      </div>
    </main>
  );
}
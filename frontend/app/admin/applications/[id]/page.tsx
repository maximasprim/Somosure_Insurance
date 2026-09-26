"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { ApplicationDetail } from "@/lib/types";

const STATUS_TONE: Record<string, "success" | "neutral" | "error" | "brand"> = {
  draft: "neutral",
  documents_required: "neutral",
  submitted: "brand",
  under_review: "brand",
  approved: "success",
  payment_pending: "brand",
  rejected: "error",
};

// Mirrors ALLOWED_STAFF_TRANSITIONS in app/services/application_service.py
// so the UI only offers valid next steps - the backend still enforces this
// independently.
const NEXT_STEPS: Record<string, string[]> = {
  submitted: ["approved", "rejected"],
};

function formatLabel(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function KeyValueGrid({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data ?? {});
  if (entries.length === 0) return <p className="text-sm text-ink-soft">None provided.</p>;
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">{formatLabel(key)}</dt>
          <dd className="mt-0.5 break-words text-sm text-ink">{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function AdminApplicationDetailPage({ params }: { params: { id: string } }) {
  const [application, setApplication] = useState<ApplicationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);

  async function load() {
    try {
      setApplication(await api.get<ApplicationDetail>(`/api/v1/admin/applications/${params.id}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load this application - are you logged in as staff?");
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
      await api.post(`/api/v1/admin/applications/${application.id}/transition`, {
        to_status: toStatus,
        notes: notes.trim() || undefined,
      });
      setNotes("");
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
        `/api/v1/admin/applications/${application.id}/documents/${documentId}/url`
      );
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setDocError(e instanceof Error ? e.message : "Could not open that document");
    }
  }

  if (error && !application) {
    return <main className="mx-auto max-w-8xl px-6 py-12 text-status-error">{error}</main>;
  }
  if (!application) {
    return <main className="mx-auto max-w-8xl px-6 py-12 text-ink-soft">Loading…</main>;
  }

  const nextSteps = NEXT_STEPS[application.status] ?? [];

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <Link href="/admin/applications" className="text-sm text-ink-soft hover:underline">
        ← Back to applications
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
            <h2 className="font-semibold">Applicant details</h2>
            <p className="mt-1 text-xs text-ink-soft">Everything submitted on the application form.</p>
            <div className="mt-4">
              <KeyValueGrid data={application.applicant_details} />
            </div>
          </Card>

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
            </dl>
          </Card>

          {application.vehicle && (
            <Card>
              <h2 className="font-semibold">Vehicle</h2>
              <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Registration</dt>
                  <dd className="mt-0.5 text-sm text-ink">{application.vehicle.registration_number}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Make / Model</dt>
                  <dd className="mt-0.5 text-sm text-ink">
                    {application.vehicle.make} {application.vehicle.model} ({application.vehicle.year})
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Chassis number</dt>
                  <dd className="mt-0.5 text-sm text-ink">{application.vehicle.chassis_number ?? "-"}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Engine number</dt>
                  <dd className="mt-0.5 text-sm text-ink">{application.vehicle.engine_number ?? "-"}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Value</dt>
                  <dd className="mt-0.5 text-sm text-ink">KES {application.vehicle.value}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Usage</dt>
                  <dd className="mt-0.5 text-sm text-ink">{application.vehicle.usage}</dd>
                </div>
              </dl>
            </Card>
          )}

          {application.insured_asset && (
            <Card>
              <h2 className="font-semibold">Insured asset</h2>
              <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Category</dt>
                  <dd className="mt-0.5 text-sm text-ink">{application.insured_asset.category}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Value</dt>
                  <dd className="mt-0.5 text-sm text-ink">
                    {application.insured_asset.value ? `KES ${application.insured_asset.value}` : "-"}
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Description</dt>
                  <dd className="mt-0.5 text-sm text-ink">{application.insured_asset.description ?? "-"}</dd>
                </div>
              </dl>
              <div className="mt-4">
                <KeyValueGrid data={application.insured_asset.details} />
              </div>
            </Card>
          )}

          <Card>
            <h2 className="font-semibold">Quote &amp; coverage</h2>
            <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Provider</dt>
                <dd className="mt-0.5 text-sm text-ink">
                  {application.quote.provider_name}
                  {application.quote.underlying_provider_name ? ` (via ${application.quote.underlying_provider_name})` : ""}
                  {application.quote.is_mock && <span className="ml-2 text-xs text-status-error">mock</span>}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Product</dt>
                <dd className="mt-0.5 text-sm text-ink">{application.quote.product_name ?? "-"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Premium</dt>
                <dd className="mt-0.5 text-sm text-ink">
                  {application.quote.currency} {application.quote.premium}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink-soft">Total (incl. taxes &amp; fees)</dt>
                <dd className="mt-0.5 text-sm text-ink">
                  {application.quote.currency} {application.quote.total}
                </dd>
              </div>
            </dl>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div>
                <h3 className="text-xs font-medium uppercase tracking-wide text-ink-soft">Coverage</h3>
                <div className="mt-2"><KeyValueGrid data={application.quote.coverage} /></div>
              </div>
              <div>
                <h3 className="text-xs font-medium uppercase tracking-wide text-ink-soft">Exclusions</h3>
                <div className="mt-2"><KeyValueGrid data={application.quote.exclusions} /></div>
              </div>
              <div>
                <h3 className="text-xs font-medium uppercase tracking-wide text-ink-soft">Deductibles</h3>
                <div className="mt-2"><KeyValueGrid data={application.quote.deductibles} /></div>
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="font-semibold">Documents</h2>
            {docError && <p className="mt-2 text-sm text-status-error">{docError}</p>}
            <div className="mt-4 flex flex-col gap-2">
              {application.documents.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between rounded-control border border-neutral-border px-4 py-2.5">
                  <div>
                    <p className="text-sm font-medium text-ink">{formatLabel(doc.document_type)}</p>
                    <p className="text-xs text-ink-soft">
                      {doc.original_filename} · {doc.status} · {new Date(doc.uploaded_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Button variant="ghost" onClick={() => viewDocument(doc.id)}>
                    View
                  </Button>
                </div>
              ))}
              {application.documents.length === 0 && <p className="text-sm text-ink-soft">No documents uploaded.</p>}
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
                <p className="mt-1 text-xs text-ink-soft">
                  Approving sends this application to the next stage (payment). Rejecting declines it.
                </p>
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
                <div className="mt-3 flex flex-col gap-2">
                  {nextSteps.map((step) => (
                    <Button
                      key={step}
                      variant={step === "rejected" ? "ghost" : "primary"}
                      disabled={busy}
                      onClick={() => decide(step)}
                    >
                      {step === "approved" ? "Approve - send to next stage" : "Decline application"}
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
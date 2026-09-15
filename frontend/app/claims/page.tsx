"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api, isLoggedIn } from "@/lib/api";
import type { Claim, CustomerProfile, DashboardData } from "@/lib/types";

const STATUS_TONE: Record<string, "success" | "neutral" | "error" | "brand"> = {
  reported: "neutral",
  documents_required: "neutral",
  submitted: "brand",
  under_review: "brand",
  insurer_review: "brand",
  approved: "success",
  settled: "success",
  rejected: "error",
  closed: "neutral",
};

function ClaimRow({ claim, onChanged }: { claim: Claim; onChanged: () => void }) {
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const needsAction = claim.status === "reported" || claim.status === "documents_required";

  async function handleUpload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/v1/claims/${claim.id}/documents?document_type=incident_photo`,
        { method: "POST", body: form }
      );
      if (!res.ok) throw new Error("Upload failed");
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleSubmitClaim() {
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/api/v1/claims/${claim.id}/submit`, {});
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit - upload at least one document first");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-sm">{claim.reference}</p>
          <p className="mt-1 text-xs text-ink-soft">{claim.incident_description}</p>
        </div>
        <Badge tone={STATUS_TONE[claim.status] ?? "neutral"}>{claim.status.replace(/_/g, " ")}</Badge>
      </div>
      {needsAction && (
        <div className="flex flex-wrap items-center gap-3 border-t border-neutral-border pt-3">
          <label className="cursor-pointer text-sm font-semibold text-brand-deep hover:underline">
            {uploading ? "Uploading…" : "Upload supporting document"}
            <input
              type="file"
              accept="application/pdf,image/jpeg,image/png"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleUpload(file);
              }}
            />
          </label>
          <Button size="md" variant="ghost" onClick={handleSubmitClaim} disabled={submitting}>
            {submitting ? "Submitting…" : "Submit claim"}
          </Button>
        </div>
      )}
      {error && <p className="text-xs text-status-error">{error}</p>}
    </Card>
  );
}

export default function ClaimsPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [policies, setPolicies] = useState<DashboardData["active_policies"]>([]);
  const [customer, setCustomer] = useState<CustomerProfile | null>(null);
  const [form, setForm] = useState({ policy_id: "", incident_date: "", incident_description: "", incident_location: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const [claimsData, profile, dashboard] = await Promise.all([
      api.get<Claim[]>("/api/v1/me/claims"),
      api.get<CustomerProfile>("/api/v1/me"),
      api.get<DashboardData>("/api/v1/me/dashboard"),
    ]);
    setClaims(claimsData);
    setCustomer(profile);
    setPolicies(dashboard.active_policies);
  }

  useEffect(() => {
    if (!isLoggedIn()) {
      window.location.href = "/login";
      return;
    }
    load().catch((e) => setError(e instanceof Error ? e.message : "Could not load your claims"));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!customer) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/claims", { ...form, customer_id: customer.id });
      setForm({ policy_id: "", incident_date: "", incident_description: "", incident_location: "" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not report the claim");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-bold">Claims</h1>
      <p className="mt-1 text-ink-soft">Report an incident or check the status of an existing claim.</p>

      <Card className="mt-6">
        <h2 className="font-semibold">Report a claim</h2>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-ink">Which policy?</label>
            <select
              required
              value={form.policy_id}
              onChange={(e) => setForm({ ...form, policy_id: e.target.value })}
              className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm"
            >
              <option value="">Select a policy</option>
              {policies.map((p) => (
                <option key={p.id} value={p.id}>{p.policy_number}</option>
              ))}
            </select>
          </div>
          <Input
            label="Incident date"
            type="date"
            required
            value={form.incident_date}
            onChange={(e) => setForm({ ...form, incident_date: e.target.value })}
          />
          <Input
            label="Location (optional)"
            value={form.incident_location}
            onChange={(e) => setForm({ ...form, incident_location: e.target.value })}
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-ink">What happened?</label>
            <textarea
              required
              rows={3}
              value={form.incident_description}
              onChange={(e) => setForm({ ...form, incident_description: e.target.value })}
              className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm"
            />
          </div>
          {error && <p className="text-sm text-status-error">{error}</p>}
          <Button type="submit" disabled={busy || policies.length === 0}>
            {busy ? "Submitting…" : "Report claim"}
          </Button>
          {policies.length === 0 && <p className="text-xs text-ink-soft">You need an active policy to report a claim.</p>}
        </form>
      </Card>

      <h2 className="mt-10 text-lg font-semibold">Your claims</h2>
      <div className="mt-3 flex flex-col gap-3">
        {claims.map((c) => (
          <ClaimRow key={c.id} claim={c} onChanged={load} />
        ))}
        {claims.length === 0 && <p className="text-ink-soft">No claims reported yet.</p>}
      </div>
    </main>
  );
}

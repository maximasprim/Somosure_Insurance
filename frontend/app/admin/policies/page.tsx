"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

interface PolicyRow {
  id: string;
  policy_number: string;
  customer_name: string;
  provider_name: string;
  status: string;
  payment_status: string;
  premium: string;
  start_date: string;
  end_date: string;
  is_mock: boolean;
  valuation_pending?: boolean;
  valuation_due?: string | null;
}

const STATUSES = ["quote", "application", "under_review", "approved", "payment_pending", "active", "expired", "cancelled", "renewal_pending", "renewed", "rejected"];

function formatKES(amount: string) {
  return `KES ${Number(amount).toLocaleString("en-KE", { maximumFractionDigits: 0 })}`;
}

export default function AdminPoliciesPage() {
  const [policies, setPolicies] = useState<PolicyRow[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [waitingOnly, setWaitingOnly] = useState(false);
  const [clearing, setClearing] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (status) params.set("status", status);
      if (waitingOnly) params.set("valuation_pending", "true");
      setPolicies(await api.get<PolicyRow[]>(`/api/v1/admin/policies?${params.toString()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load policies");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, waitingOnly]);

  // Clears the "waiting for valuation report" flag. It changes nothing else: the premium is reconciled separately.
  async function valuationReceived(p: PolicyRow) {
    if (!window.confirm(`Mark the valuation report for ${p.policy_number} as received?\n\nThis only clears the flag. Reconcile the premium to the actual value separately.`)) return;
    setClearing(p.id);
    setError(null);
    try {
      await api.post(`/api/v1/admin/policies/${p.id}/valuation-received`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update the policy");
    } finally {
      setClearing(null);
    }
  }

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <h1 className="text-2xl font-bold">Policies</h1>
      <p className="mt-1 text-ink-soft">Every issued policy across all providers.</p>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <div className="flex-1">
          <Input
            label="Search by policy number or customer"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-ink">Status</label>
          <select
            className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" checked={waitingOnly} onChange={(e) => setWaitingOnly(e.target.checked)} />
          Waiting for valuation report
        </label>
        <Button variant="ghost" onClick={load}>
          Search
        </Button>
      </div>

      <div className="mt-4 flex flex-col gap-2">
        {loading && <p className="text-ink-soft">Loading…</p>}
        {!loading && policies.length === 0 && <p className="text-ink-soft">No policies found.</p>}
        {!loading &&
          policies.map((p) => (
            <Card key={p.id} className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-mono text-sm font-semibold">{p.policy_number}</h3>
                  <Badge tone="brand">{p.status.replace(/_/g, " ")}</Badge>
                  {p.payment_status !== "paid" && <Badge tone="error">{p.payment_status.replace(/_/g, " ")}</Badge>}
                  {p.is_mock && <Badge tone="neutral">Mock</Badge>}
                  {p.valuation_pending && (
                    <Badge tone="info">Valuation pending{p.valuation_due ? ` · one-month sticker to ${p.valuation_due}` : ""}</Badge>
                  )}
                </div>
                <p className="mt-1 text-xs text-ink-soft">
                  {p.customer_name} · {p.provider_name} · {p.start_date} to {p.end_date}
                </p>
              </div>
              <div className="flex items-center gap-3">
                {p.valuation_pending && (
                  <Button variant="ghost" onClick={() => valuationReceived(p)} disabled={clearing === p.id}>
                    {clearing === p.id ? "Saving…" : "Valuation received"}
                  </Button>
                )}
                <span className="font-semibold">{formatKES(p.premium)}</span>
              </div>
            </Card>
          ))}
      </div>
    </main>
  );
}

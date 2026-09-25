"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

interface RenewalRow {
  id: string;
  policy_number: string;
  customer_name: string;
  due_date: string;
  status: string;
}

const STATUSES = ["due", "contacted", "quoted", "paid", "renewed", "lost"];

function toneFor(status: string): "success" | "error" | "brand" | "neutral" {
  if (status === "renewed" || status === "paid") return "success";
  if (status === "lost") return "error";
  if (status === "due") return "brand";
  return "neutral";
}

const selectClass = "rounded-control border border-neutral-border bg-white px-2 py-1.5 text-xs";

export default function AdminRenewalsPage() {
  const [renewals, setRenewals] = useState<RenewalRow[]>([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      setRenewals(await api.get<RenewalRow[]>(`/api/v1/admin/renewals?${params.toString()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load renewals");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  async function updateStatus(r: RenewalRow, newStatus: string) {
    await api.patch(`/api/v1/admin/renewals/${r.id}`, { status: newStatus });
    load();
  }

  const today = new Date();

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-2xl font-bold">Renewals</h1>
      <p className="mt-1 text-ink-soft">
        Every policy renewal being tracked. The automation page can trigger the reminder scan; this is where you see
        what it found.
      </p>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <div className="mt-6 flex flex-col gap-1.5">
        <label className="text-sm font-medium text-ink">Status</label>
        <select
          className="w-fit rounded-control border border-neutral-border bg-white px-3 py-2 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4 flex flex-col gap-2">
        {loading && <p className="text-ink-soft">Loading…</p>}
        {!loading && renewals.length === 0 && <p className="text-ink-soft">No renewals found.</p>}
        {!loading &&
          renewals.map((r) => {
            const overdue = r.status === "due" && new Date(r.due_date) < today;
            return (
              <Card key={r.id} className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-mono text-sm font-semibold">{r.policy_number}</h3>
                    <Badge tone={toneFor(r.status)}>{r.status}</Badge>
                    {overdue && <Badge tone="error">Overdue</Badge>}
                  </div>
                  <p className="mt-1 text-xs text-ink-soft">
                    {r.customer_name} · due {r.due_date}
                  </p>
                </div>
                <select className={selectClass} value={r.status} onChange={(e) => updateStatus(r, e.target.value)}>
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </Card>
            );
          })}
      </div>
    </main>
  );
}

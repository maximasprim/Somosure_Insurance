"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

interface PaymentRow {
  id: string;
  reference: string;
  customer_name: string;
  amount: string;
  currency: string;
  method: string;
  status: string;
  created_at: string;
}

const STATUSES = ["initiated", "pending", "successful", "failed", "reversed", "refunded"];

function toneFor(status: string): "success" | "error" | "brand" | "neutral" {
  if (status === "successful") return "success";
  if (status === "failed" || status === "reversed") return "error";
  if (status === "pending" || status === "initiated") return "brand";
  return "neutral";
}

export default function AdminPaymentsPage() {
  const [payments, setPayments] = useState<PaymentRow[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (status) params.set("status", status);
      setPayments(await api.get<PaymentRow[]>(`/api/v1/admin/payments?${params.toString()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load payments");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <h1 className="text-2xl font-bold">Payments</h1>
      <p className="mt-1 text-ink-soft">Every payment intent across the platform.</p>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <div className="flex-1">
          <Input
            label="Search by reference or customer"
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
                {s}
              </option>
            ))}
          </select>
        </div>
        <Button variant="ghost" onClick={load}>
          Search
        </Button>
      </div>

      <div className="mt-4 flex flex-col gap-2">
        {loading && <p className="text-ink-soft">Loading…</p>}
        {!loading && payments.length === 0 && <p className="text-ink-soft">No payments found.</p>}
        {!loading &&
          payments.map((p) => (
            <Card key={p.id} className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-mono text-sm font-semibold">{p.reference}</h3>
                  <Badge tone={toneFor(p.status)}>{p.status}</Badge>
                  <Badge tone="neutral">{p.method}</Badge>
                </div>
                <p className="mt-1 text-xs text-ink-soft">
                  {p.customer_name} · {new Date(p.created_at).toLocaleString("en-KE")}
                </p>
              </div>
              <span className="font-semibold">
                {p.currency} {Number(p.amount).toLocaleString("en-KE", { maximumFractionDigits: 0 })}
              </span>
            </Card>
          ))}
      </div>
    </main>
  );
}

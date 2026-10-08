"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { AffiliateCommissionPage, AffiliateCommissionRow, AffiliateSummary, CommissionStatus } from "@/lib/types";
import { categoryLabel, inputClass, kes } from "@/components/affiliate/shared";

const PAGE = 25;
const TONE: Record<CommissionStatus, "success" | "error" | "brand" | "neutral" | "info"> = {
  pending: "info",
  approved: "brand",
  paid: "success",
  reversed: "error",
  rejected: "error",
};
const FILTERS: { key: "" | CommissionStatus; label: string }[] = [
  { key: "pending", label: "Needs approval" },
  { key: "approved", label: "Ready to pay" },
  { key: "paid", label: "Paid" },
  { key: "reversed", label: "Reversed" },
  { key: "rejected", label: "Rejected" },
  { key: "", label: "All" },
];

type Pending = { id: string; kind: "pay" | "reject" | "reverse" } | null;

export function CommissionsTab() {
  const [status, setStatus] = useState<"" | CommissionStatus>("pending");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<AffiliateCommissionPage | null>(null);
  const [summary, setSummary] = useState<AffiliateSummary | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [action, setAction] = useState<Pending>(null);
  const [text, setText] = useState("");
  const [bulkRef, setBulkRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (nextOffset = 0) => {
      setError(null);
      try {
        const params = new URLSearchParams({ limit: String(PAGE), offset: String(nextOffset) });
        if (status) params.set("status", status);
        if (q.trim()) params.set("q", q.trim());
        const [list, sum] = await Promise.all([
          api.get<AffiliateCommissionPage>(`/api/v1/admin/affiliate-program/commissions?${params}`),
          api.get<AffiliateSummary>("/api/v1/admin/affiliate-program/summary"),
        ]);
        setPage(list);
        setSummary(sum);
        setOffset(nextOffset);
        setSelected(new Set());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load commissions");
      }
    },
    [status, q]
  );

  useEffect(() => {
    load(0);
  }, [load]);

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await fn();
      setMessage(label);
      setAction(null);
      setText("");
      await load(offset);
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work");
    } finally {
      setBusy(false);
    }
  }

  const base = "/api/v1/admin/affiliate-program/commissions";
  const approve = (c: AffiliateCommissionRow) => run("Approved.", () => api.post(`${base}/${c.id}/approve`));
  const submitAction = (c: AffiliateCommissionRow) => {
    if (!action) return;
    if (action.kind === "pay") return run("Marked as paid.", () => api.post(`${base}/${c.id}/pay`, { payout_reference: text, payout_method: "mpesa" }));
    const word = action.kind === "reject" ? "Rejected." : "Reversed.";
    return run(word, () => api.post(`${base}/${c.id}/${action.kind}`, { reason: text }, { reason: text }));
  };
  const bulk = (kind: "approve" | "pay") =>
    run(kind === "approve" ? "Approved the selection." : "Marked the selection as paid.", async () => {
      const res = await api.post<{ done: number; failed: { id: string; error: string }[] }>(`${base}/bulk`, {
        action: kind,
        ids: Array.from(selected),
        payout_reference: kind === "pay" ? bulkRef : undefined,
      });
      if (res.failed.length) throw new Error(`${res.done} done, ${res.failed.length} could not be processed: ${res.failed[0].error}`);
    });

  const items = page?.items ?? [];
  const allChecked = items.length > 0 && items.every((i) => selected.has(i.id));
  const total = page?.total ?? 0;

  return (
    <div className="flex flex-col gap-5">
      {summary && (
        <div className="grid gap-3 sm:grid-cols-3">
          <SummaryBox label="Needs approval" count={summary.pending_count} amount={summary.pending_amount} />
          <SummaryBox label="Ready to pay" count={summary.approved_count} amount={summary.approved_amount} />
          <SummaryBox label="Paid out" count={summary.paid_count} amount={summary.paid_amount} />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => { setStatus(f.key); }}
            className={`rounded-full px-4 py-1.5 text-sm font-semibold ${status === f.key ? "bg-brand-deep text-white" : "bg-neutral text-ink-soft hover:text-ink"}`}
          >
            {f.label}
          </button>
        ))}
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(0)}
          placeholder="Search referrer or payout reference"
          className={`${inputClass} ml-auto max-w-xs`}
        />
      </div>

      {message && <p className="rounded-control bg-status-success/10 px-4 py-2 text-sm text-status-success">{message}</p>}
      {error && <p className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      {selected.size > 0 && (
        <Card className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium">{selected.size} selected</span>
          <Button size="md" disabled={busy} onClick={() => bulk("approve")}>Approve</Button>
          <input value={bulkRef} onChange={(e) => setBulkRef(e.target.value)} placeholder="Payout reference for all" className={`${inputClass} max-w-xs`} />
          <Button size="md" variant="secondary" disabled={busy || !bulkRef.trim()} onClick={() => bulk("pay")}>Mark paid</Button>
        </Card>
      )}

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="bg-neutral text-xs uppercase text-ink-soft">
            <tr>
              <th className="px-3 py-3"><input type="checkbox" checked={allChecked} onChange={(e) => setSelected(e.target.checked ? new Set(items.map((i) => i.id)) : new Set())} aria-label="Select all" /></th>
              <th className="px-3 py-3">Earned by</th>
              <th className="px-3 py-3">From</th>
              <th className="px-3 py-3">Policy</th>
              <th className="px-3 py-3">Rate</th>
              <th className="px-3 py-3 text-right">Commission</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} className="border-t border-neutral-border align-top">
                <td className="px-3 py-3"><input type="checkbox" checked={selected.has(c.id)} onChange={(e) => { const n = new Set(selected); e.target.checked ? n.add(c.id) : n.delete(c.id); setSelected(n); }} aria-label="Select" /></td>
                <td className="px-3 py-3">
                  <p className="font-medium text-ink">{c.referrer_name}</p>
                  <p className="text-xs text-ink-soft">Pay to {c.payout_phone ?? c.referrer_phone}</p>
                </td>
                <td className="px-3 py-3">
                  <p className="text-ink">{c.referred_name}</p>
                  <p className="text-xs text-ink-soft">{new Date(c.created_at).toLocaleDateString()}</p>
                </td>
                <td className="px-3 py-3">
                  <p className="font-mono text-xs text-ink">{c.policy_number ?? "(policy removed)"}</p>
                  <p className="text-xs text-ink-soft">{categoryLabel(c.category)} · {kes(c.premium)}</p>
                </td>
                <td className="px-3 py-3 text-xs text-ink-soft">
                  {c.rate_type === "percent" ? `${Number(c.rate_value)}%` : kes(c.rate_value)}
                  {c.rate_label && <p>{c.rate_label}</p>}
                </td>
                <td className="px-3 py-3 text-right font-semibold">{kes(c.commission_amount)}</td>
                <td className="px-3 py-3">
                  <Badge tone={TONE[c.status]}>{c.status}</Badge>
                  {c.payout_reference && <p className="mt-1 text-xs text-ink-soft">Ref {c.payout_reference}</p>}
                  {c.status_note && <p className="mt-1 max-w-[12rem] text-xs text-ink-soft">“{c.status_note}”</p>}
                </td>
                <td className="px-3 py-3">
                  {action?.id === c.id ? (
                    <div className="flex min-w-[14rem] flex-col gap-2">
                      <input
                        autoFocus
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        placeholder={action.kind === "pay" ? "M-Pesa code / reference" : "Reason (required)"}
                        className={inputClass}
                      />
                      <div className="flex gap-2">
                        <Button size="md" disabled={busy || !text.trim()} onClick={() => submitAction(c)}>Confirm {action.kind === "pay" ? "payment" : action.kind}</Button>
                        <Button size="md" variant="ghost" onClick={() => { setAction(null); setText(""); }}>Cancel</Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-start gap-1 text-xs font-semibold">
                      {c.status === "pending" && <button type="button" disabled={busy} onClick={() => approve(c)} className="text-brand-deep hover:underline">Approve</button>}
                      {c.status === "approved" && <button type="button" onClick={() => { setAction({ id: c.id, kind: "pay" }); setText(""); }} className="text-brand-deep hover:underline">Mark paid…</button>}
                      {(c.status === "pending" || c.status === "approved") && <button type="button" onClick={() => { setAction({ id: c.id, kind: "reject" }); setText(""); }} className="text-status-error hover:underline">Reject…</button>}
                      {(c.status === "approved" || c.status === "paid") && <button type="button" onClick={() => { setAction({ id: c.id, kind: "reverse" }); setText(""); }} className="text-status-error hover:underline">Reverse…</button>}
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {page && items.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-10 text-center text-ink-soft">Nothing here. Commissions appear when someone you referred gets insured.</td></tr>
            )}
          </tbody>
        </table>
      </Card>

      <div className="flex items-center justify-between text-sm text-ink-soft">
        <span>{total === 0 ? "0" : `${offset + 1}–${Math.min(offset + PAGE, total)} of ${total}`}</span>
        <div className="flex gap-2">
          <Button variant="ghost" disabled={offset === 0} onClick={() => load(Math.max(0, offset - PAGE))}>← Newer</Button>
          <Button variant="ghost" disabled={offset + PAGE >= total} onClick={() => load(offset + PAGE)}>Older →</Button>
        </div>
      </div>
    </div>
  );
}

function SummaryBox({ label, count, amount }: { label: string; count: number; amount: string }) {
  return (
    <Card>
      <p className="text-xs text-ink-soft">{label}</p>
      <p className="mt-1 text-xl font-bold text-ink">{kes(amount)}</p>
      <p className="text-xs text-ink-soft">{count} commission{count === 1 ? "" : "s"}</p>
    </Card>
  );
}

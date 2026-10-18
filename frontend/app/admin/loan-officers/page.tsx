"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { COMMISSION_LABELS, kes, type LoanOfficerSummary, type OfficerCommission } from "@/lib/ipf";

const INPUT = "w-full rounded-control border border-neutral-border bg-white px-3 py-2 text-sm";

const STATUS_TONE: Record<OfficerCommission["status"], "neutral" | "success" | "error" | "brand" | "info"> = {
  awaiting_basis: "brand",
  pending: "info",
  approved: "info",
  paid: "success",
  cancelled: "neutral",
};

function TargetBar({ pct }: { pct: number | null }) {
  if (pct === null) return <span className="text-xs text-ink-soft">No target</span>;
  const width = Math.min(100, Math.max(0, pct));
  return (
    <div className="w-32">
      <div className="h-2 overflow-hidden rounded-full bg-neutral">
        <div className="h-full rounded-full" style={{ width: `${width}%`, background: pct >= 100 ? "#1F9254" : "#FFC53D" }} />
      </div>
      <span className="text-[11px] text-ink-soft">{pct}% of target</span>
    </div>
  );
}

export default function LoanOfficersPage() {
  const [officers, setOfficers] = useState<LoanOfficerSummary[]>([]);
  const [commissions, setCommissions] = useState<OfficerCommission[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [form, setForm] = useState({ full_name: "", staff_number: "", phone: "", email: "", monthly_target: "" });
  const [basis, setBasis] = useState<Record<string, string>>({});
  const [payout, setPayout] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const [o, c] = await Promise.all([
        api.get<LoanOfficerSummary[]>("/api/v1/admin/loan-officers"),
        api.get<OfficerCommission[]>(`/api/v1/admin/loan-officers/commissions${filter ? `?status_filter=${filter}` : ""}`),
      ]);
      setOfficers(o);
      setCommissions(c);
      setForbidden(false);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Could not load loan officers";
      if (/insufficient permissions|403/i.test(message)) setForbidden(true);
      else setError(message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  async function act(work: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await work();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work - please try again");
    } finally {
      setBusy(false);
    }
  }

  const addOfficer = () =>
    act(async () => {
      await api.post("/api/v1/admin/loan-officers", {
        full_name: form.full_name,
        staff_number: form.staff_number,
        phone: form.phone || null,
        email: form.email || null,
        monthly_target: form.monthly_target || null,
      });
      setForm({ full_name: "", staff_number: "", phone: "", email: "", monthly_target: "" });
    });

  if (forbidden) {
    return (
      <main className="mx-auto max-w-8xl px-3 py-4">
        <h1 className="text-2xl font-bold">Loan officers</h1>
        <Card className="mt-6 text-sm text-ink-soft">Loan officers and their commission are available to management and finance roles.</Card>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <h1 className="text-2xl font-bold">Loan officers</h1>
      <p className="mt-1 text-sm text-ink-soft">
        Bidii Credit officers who bring in IPF sales, their monthly targets, and the commission they earn on financed policies.
      </p>
      {error && <p className="mt-3 text-sm text-status-error">{error}</p>}

      <Card className="mt-6">
        <h2 className="text-sm font-semibold">Add a loan officer</h2>
        <div className="mt-3 grid gap-2 sm:grid-cols-5">
          <input className={INPUT} placeholder="Full name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          <input className={INPUT} placeholder="Staff number (the code customers quote)" value={form.staff_number} onChange={(e) => setForm({ ...form, staff_number: e.target.value })} />
          <input className={INPUT} placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          <input className={INPUT} placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input className={INPUT} type="number" min="0" placeholder="Monthly target (KES)" value={form.monthly_target} onChange={(e) => setForm({ ...form, monthly_target: e.target.value })} />
        </div>
        <div className="mt-3">
          <Button onClick={addOfficer} disabled={busy || form.full_name.trim().length < 2 || form.staff_number.trim().length < 2}>
            Add officer
          </Button>
        </div>
      </Card>

      <Card className="mt-6 overflow-x-auto">
        <h2 className="text-sm font-semibold">Officers &amp; this month</h2>
        {loading ? (
          <p className="mt-3 text-sm text-ink-soft">Loading…</p>
        ) : officers.length === 0 ? (
          <p className="mt-3 text-sm text-ink-soft">No loan officers yet.</p>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <thead className="text-xs text-ink-soft">
              <tr>
                <th className="py-2 pr-4 font-medium">Officer</th>
                <th className="py-2 pr-4 font-medium">Financed this month</th>
                <th className="py-2 pr-4 font-medium">Target</th>
                <th className="py-2 pr-4 text-right font-medium">Pending</th>
                <th className="py-2 pr-4 text-right font-medium">Approved</th>
                <th className="py-2 pr-4 text-right font-medium">Paid</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {officers.map((o) => (
                <tr key={o.id} className="border-t border-neutral-border/60">
                  <td className="py-3 pr-4">
                    <span className="font-medium text-ink">{o.full_name}</span>
                    <span className="ml-2 text-xs text-ink-soft">{o.staff_number}</span>
                    {!o.is_active && <Badge className="ml-2" tone="neutral">Inactive</Badge>}
                  </td>
                  <td className="py-3 pr-4">
                    {kes(o.financed_this_month)} <span className="text-xs text-ink-soft">({o.requests_this_month} approved)</span>
                  </td>
                  <td className="py-3 pr-4">
                    <TargetBar pct={o.target_progress_pct} />
                    {o.monthly_target && <span className="text-[11px] text-ink-soft">of {kes(o.monthly_target)}</span>}
                  </td>
                  <td className="py-3 pr-4 text-right">{kes(o.commission_pending)}</td>
                  <td className="py-3 pr-4 text-right">{kes(o.commission_approved)}</td>
                  <td className="py-3 pr-4 text-right font-medium">{kes(o.commission_paid)}</td>
                  <td className="py-3 text-right">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => act(() => api.patch(`/api/v1/admin/loan-officers/${o.id}`, { is_active: !o.is_active }))}
                      className="text-xs font-semibold text-brand-deep hover:underline"
                    >
                      {o.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card className="mt-6 overflow-x-auto">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">Commission</h2>
          <select className="rounded-control border border-neutral-border bg-white px-3 py-1.5 text-sm" value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">All</option>
            {Object.entries(COMMISSION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <p className="mt-1 text-xs text-ink-soft">
          Opened automatically when a financed policy is issued. Enter Somosure&apos;s net commission on the policy and the officer&apos;s share is worked out from it.
        </p>
        {commissions.length === 0 ? (
          <p className="mt-3 text-sm text-ink-soft">Nothing here yet.</p>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <thead className="text-xs text-ink-soft">
              <tr>
                <th className="py-2 pr-4 font-medium">Officer</th>
                <th className="py-2 pr-4 font-medium">Financing / policy</th>
                <th className="py-2 pr-4 text-right font-medium">Somosure net commission</th>
                <th className="py-2 pr-4 text-right font-medium">Officer share</th>
                <th className="py-2 pr-4 font-medium">Status</th>
                <th className="py-2 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {commissions.map((c) => (
                <tr key={c.id} className="border-t border-neutral-border/60 align-top">
                  <td className="py-3 pr-4">{c.loan_officer_name}</td>
                  <td className="py-3 pr-4 text-xs">
                    <div>{c.financing_reference}</div>
                    <div className="text-ink-soft">{c.policy_number ?? "-"}</div>
                  </td>
                  <td className="py-3 pr-4 text-right">{kes(c.somosure_net_commission)}</td>
                  <td className="py-3 pr-4 text-right">
                    <span className="font-medium">{kes(c.commission_amount)}</span>
                    <div className="text-[11px] text-ink-soft">at {Number(c.rate_pct)}%</div>
                  </td>
                  <td className="py-3 pr-4">
                    <Badge tone={STATUS_TONE[c.status]}>{COMMISSION_LABELS[c.status]}</Badge>
                    {c.payout_reference && <div className="mt-1 text-[11px] text-ink-soft">Ref {c.payout_reference}</div>}
                  </td>
                  <td className="py-3">
                    {(c.status === "awaiting_basis" || c.status === "pending") && (
                      <div className="mb-2 flex gap-2">
                        <input
                          className="w-32 rounded-control border border-neutral-border px-2 py-1 text-xs"
                          type="number"
                          min="0"
                          placeholder="Net commission"
                          value={basis[c.id] ?? ""}
                          onChange={(e) => setBasis({ ...basis, [c.id]: e.target.value })}
                        />
                        <Button
                          variant="ghost"
                          disabled={busy || !basis[c.id]}
                          onClick={() => act(() => api.post(`/api/v1/admin/loan-officers/commissions/${c.id}/basis`, { net_commission: basis[c.id] }))}
                        >
                          Set
                        </Button>
                      </div>
                    )}
                    <div className="flex flex-wrap items-center gap-2">
                      {c.status === "pending" && (
                        <Button variant="ghost" disabled={busy} onClick={() => act(() => api.post(`/api/v1/admin/loan-officers/commissions/${c.id}/transition`, { to_status: "approved" }))}>
                          Approve
                        </Button>
                      )}
                      {c.status === "approved" && (
                        <>
                          <input
                            className="w-28 rounded-control border border-neutral-border px-2 py-1 text-xs"
                            placeholder="Payout ref"
                            value={payout[c.id] ?? ""}
                            onChange={(e) => setPayout({ ...payout, [c.id]: e.target.value })}
                          />
                          <Button
                            variant="ghost"
                            disabled={busy}
                            onClick={() => act(() => api.post(`/api/v1/admin/loan-officers/commissions/${c.id}/transition`, { to_status: "paid", payout_reference: payout[c.id] || undefined }))}
                          >
                            Mark paid
                          </Button>
                        </>
                      )}
                      {["awaiting_basis", "pending", "approved"].includes(c.status) && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => window.confirm("Cancel this commission?") && act(() => api.post(`/api/v1/admin/loan-officers/commissions/${c.id}/transition`, { to_status: "cancelled" }))}
                          className="text-xs text-status-error hover:underline"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </main>
  );
}

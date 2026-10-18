"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { APPLIES_LABEL, amountRange, kes, termRange, type RatePreview, type RateTier } from "@/lib/pricing";

const INPUT = "w-full rounded-control border border-neutral-border bg-white px-3 py-2 text-sm";

const EMPTY = { label: "", applies_to: "all", min_amount: "0", max_amount: "", min_term_months: "3", max_term_months: "", interest_rate_monthly: "" };

/**
 * Pricing tiers for Bidii Credit IPF: the monthly interest rate by loan amount and term.
 * With no tiers the standard rate applies exactly as before. A loan matches at most one
 * tier (overlaps are refused when you save), the existing-customer preferred rate is never
 * overridden, and amounts are matched on the amount being financed (premium less deposit).
 */
export function RateTiersCard({ canEdit }: { canEdit: boolean }) {
  const [tiers, setTiers] = useState<RateTier[] | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [check, setCheck] = useState({ amount: "", term: "6", corporate: false });
  const [preview, setPreview] = useState<RatePreview | null>(null);

  const load = useCallback(async () => {
    try {
      setTiers(await api.get<RateTier[]>("/api/v1/admin/financing/rate-tiers"));
    } catch {
      setTiers(null);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function body() {
    return {
      label: form.label.trim(),
      applies_to: form.applies_to,
      min_amount: form.min_amount === "" ? "0" : form.min_amount,
      max_amount: form.max_amount === "" ? null : form.max_amount,
      min_term_months: Number(form.min_term_months || 1),
      max_term_months: form.max_term_months === "" ? null : Number(form.max_term_months),
      interest_rate_monthly: form.interest_rate_monthly,
    };
  }

  async function run(work: () => Promise<unknown>) {
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

  const save = () =>
    run(async () => {
      if (editing) await api.patch(`/api/v1/admin/financing/rate-tiers/${editing}`, body());
      else await api.post("/api/v1/admin/financing/rate-tiers", body());
      setForm(EMPTY);
      setEditing(null);
    });

  function startEdit(t: RateTier) {
    setEditing(t.id);
    setError(null);
    setForm({
      label: t.label,
      applies_to: t.applies_to,
      min_amount: String(Number(t.min_amount)),
      max_amount: t.max_amount === null ? "" : String(Number(t.max_amount)),
      min_term_months: String(t.min_term_months),
      max_term_months: t.max_term_months === null ? "" : String(t.max_term_months),
      interest_rate_monthly: String(Number(t.interest_rate_monthly)),
    });
  }

  async function runCheck() {
    setError(null);
    try {
      const q = new URLSearchParams({ amount: check.amount, term_months: check.term, corporate: String(check.corporate) });
      setPreview(await api.get<RatePreview>(`/api/v1/admin/financing/rate-tiers/preview?${q.toString()}`));
    } catch (e) {
      setPreview(null);
      setError(e instanceof Error ? e.message : "Could not check that rate");
    }
  }

  if (tiers === null) return null;

  const valid = form.label.trim().length >= 2 && form.interest_rate_monthly !== "";

  return (
    <Card className="mt-6">
      <h2 className="text-sm font-semibold text-ink">Pricing by loan amount &amp; term</h2>
      <p className="mt-1 text-xs text-ink-soft">
        Set the monthly interest rate for loans of different sizes and terms. Amounts run from the lower figure up to, but not including, the upper one, so tiers can sit
        back to back. Leave an upper limit blank for no limit. With no tiers the standard rate applies, and customers with the existing-loan concession always keep their
        preferred rate.
      </p>
      {error && <p className="mt-3 text-sm text-status-error">{error}</p>}

      {tiers.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-ink-soft">
              <tr>
                <th className="py-2 pr-3 font-medium">Tier</th>
                <th className="py-2 pr-3 font-medium">For</th>
                <th className="py-2 pr-3 font-medium">Loan amount</th>
                <th className="py-2 pr-3 font-medium">Term</th>
                <th className="py-2 pr-3 text-right font-medium">Rate / month</th>
                <th className="py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {tiers.map((t) => (
                <tr key={t.id} className={`border-t border-neutral-border/60 ${t.is_active ? "" : "opacity-50"}`}>
                  <td className="py-2.5 pr-3 font-medium text-ink">
                    {t.label}
                    {!t.is_active && <Badge className="ml-2" tone="neutral">Off</Badge>}
                  </td>
                  <td className="py-2.5 pr-3 text-xs">{APPLIES_LABEL[t.applies_to]}</td>
                  <td className="py-2.5 pr-3 text-xs">{amountRange(t)}</td>
                  <td className="py-2.5 pr-3 text-xs">{termRange(t)}</td>
                  <td className="py-2.5 pr-3 text-right font-semibold">{Number(t.interest_rate_monthly)}%</td>
                  <td className="py-2.5 text-right text-xs">
                    {canEdit && (
                      <span className="inline-flex gap-3">
                        <button type="button" disabled={busy} className="font-semibold text-brand-deep hover:underline" onClick={() => startEdit(t)}>
                          Edit
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          className="font-semibold text-ink-soft hover:underline"
                          onClick={() => run(() => api.patch(`/api/v1/admin/financing/rate-tiers/${t.id}`, { is_active: !t.is_active }))}
                        >
                          {t.is_active ? "Turn off" : "Turn on"}
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          className="text-status-error hover:underline"
                          onClick={() => window.confirm(`Delete the tier "${t.label}"?`) && run(() => api.del(`/api/v1/admin/financing/rate-tiers/${t.id}`))}
                        >
                          Delete
                        </button>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {tiers.length === 0 && <p className="mt-4 text-sm text-ink-soft">No tiers yet - every loan uses the standard rate.</p>}

      {canEdit && (
        <div className="mt-5 rounded-control border border-neutral-border p-4">
          <p className="text-sm font-medium text-ink">{editing ? "Edit tier" : "Add a tier"}</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-4">
            <label className="text-xs text-ink-soft sm:col-span-2">
              Name
              <input className={`${INPUT} mt-1`} value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} placeholder="e.g. Loans under KES 100,000" />
            </label>
            <label className="text-xs text-ink-soft">
              Applies to
              <select className={`${INPUT} mt-1`} value={form.applies_to} onChange={(e) => setForm({ ...form, applies_to: e.target.value })}>
                <option value="all">Everyone</option>
                <option value="individual">Individuals</option>
                <option value="corporate">Companies</option>
              </select>
            </label>
            <label className="text-xs text-ink-soft">
              Rate per month (%)
              <input className={`${INPUT} mt-1`} type="number" min="0" max="100" step="0.01" value={form.interest_rate_monthly} onChange={(e) => setForm({ ...form, interest_rate_monthly: e.target.value })} />
            </label>
            <label className="text-xs text-ink-soft">
              Loan from (KES)
              <input className={`${INPUT} mt-1`} type="number" min="0" value={form.min_amount} onChange={(e) => setForm({ ...form, min_amount: e.target.value })} />
            </label>
            <label className="text-xs text-ink-soft">
              Up to, not including (KES)
              <input className={`${INPUT} mt-1`} type="number" min="0" placeholder="No limit" value={form.max_amount} onChange={(e) => setForm({ ...form, max_amount: e.target.value })} />
            </label>
            <label className="text-xs text-ink-soft">
              Term from (months)
              <input className={`${INPUT} mt-1`} type="number" min="1" value={form.min_term_months} onChange={(e) => setForm({ ...form, min_term_months: e.target.value })} />
            </label>
            <label className="text-xs text-ink-soft">
              Term up to (months)
              <input className={`${INPUT} mt-1`} type="number" min="1" placeholder="No limit" value={form.max_term_months} onChange={(e) => setForm({ ...form, max_term_months: e.target.value })} />
            </label>
          </div>
          <div className="mt-3 flex items-center gap-3">
            <Button onClick={save} disabled={busy || !valid}>
              {editing ? "Save changes" : "Add tier"}
            </Button>
            {editing && (
              <Button
                variant="ghost"
                onClick={() => {
                  setEditing(null);
                  setForm(EMPTY);
                  setError(null);
                }}
              >
                Cancel
              </Button>
            )}
          </div>
        </div>
      )}

      <div className="mt-5 border-t border-neutral-border/60 pt-4">
        <p className="text-sm font-medium text-ink">Check a rate</p>
        <div className="mt-2 grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto_auto]">
          <label className="text-xs text-ink-soft">
            Amount financed (KES)
            <input className={`${INPUT} mt-1`} type="number" min="1" value={check.amount} onChange={(e) => setCheck({ ...check, amount: e.target.value })} />
          </label>
          <label className="text-xs text-ink-soft">
            Term (months)
            <input className={`${INPUT} mt-1`} type="number" min="1" value={check.term} onChange={(e) => setCheck({ ...check, term: e.target.value })} />
          </label>
          <label className="flex items-center gap-2 pb-2 text-xs text-ink-soft">
            <input type="checkbox" checked={check.corporate} onChange={(e) => setCheck({ ...check, corporate: e.target.checked })} /> A company
          </label>
          <Button variant="ghost" onClick={runCheck} disabled={!check.amount}>
            Check
          </Button>
        </div>
        {preview && (
          <p className="mt-3 text-sm text-ink">
            {kes(check.amount)} over {check.term} months → <span className="font-semibold">{Number(preview.rate)}% a month</span>{" "}
            <span className="text-ink-soft">
              {preview.source === "tier" && preview.tier ? `(tier: ${preview.tier.label})` : preview.source === "corporate" ? "(the company rate)" : "(the standard rate)"}
            </span>
          </p>
        )}
      </div>
    </Card>
  );
}

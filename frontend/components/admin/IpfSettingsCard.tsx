"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

interface IpfSettings {
  early_settlement_fee_pct?: string | number;
  loan_officer_commission_pct?: string | number;
  somosure_commission_pct_of_premium?: string | number | null;
}

const INPUT = "w-full rounded-control border border-neutral-border bg-white px-3 py-2 text-sm";

/**
 * The three rates behind the IPF extras, saved on their own so the main rates form
 * below it is untouched:
 *   - early settlement fee: charged on the principal still owed when a loan is cleared early;
 *   - loan officer commission: their share of Somosure's net commission on a financed policy;
 *   - Somosure commission as % of premium (optional): lets officers' commission be worked
 *     out automatically; left empty, finance enters the real net commission per policy.
 */
export function IpfSettingsCard({ canEdit }: { canEdit: boolean }) {
  const [form, setForm] = useState({ early: "", officer: "", basis: "" });
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function fill(s: IpfSettings) {
    setForm({
      early: s.early_settlement_fee_pct != null ? String(Number(s.early_settlement_fee_pct)) : "",
      officer: s.loan_officer_commission_pct != null ? String(Number(s.loan_officer_commission_pct)) : "",
      basis: s.somosure_commission_pct_of_premium != null ? String(Number(s.somosure_commission_pct_of_premium)) : "",
    });
  }

  useEffect(() => {
    api
      .get<IpfSettings>("/api/v1/admin/financing/settings")
      .then((s) => {
        fill(s);
        setLoaded(true);
      })
      .catch(() => setLoaded(false));
  }, []);

  async function save() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await api.patch<IpfSettings>(
        "/api/v1/admin/financing/settings",
        {
          early_settlement_fee_pct: form.early === "" ? undefined : form.early,
          loan_officer_commission_pct: form.officer === "" ? undefined : form.officer,
          somosure_commission_pct_of_premium: form.basis === "" ? null : form.basis,
        },
        { reason: "IPF early settlement and loan officer commission rates updated" }
      );
      fill(saved);
      setMessage("Saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save these rates");
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) return null;

  return (
    <Card className="mt-6">
      <h2 className="text-sm font-semibold text-ink">Early settlement &amp; loan officer commission</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <label className="text-sm">
          <span className="font-medium text-ink">Early settlement fee (%)</span>
          <input className={`${INPUT} mt-1`} type="number" min="0" max="100" step="0.01" disabled={!canEdit || busy} value={form.early} onChange={(e) => setForm({ ...form, early: e.target.value })} />
          <span className="mt-1 block text-xs text-ink-soft">Of the principal still owed when a client clears the loan early.</span>
        </label>
        <label className="text-sm">
          <span className="font-medium text-ink">Loan officer commission (%)</span>
          <input className={`${INPUT} mt-1`} type="number" min="0" max="100" step="0.01" disabled={!canEdit || busy} value={form.officer} onChange={(e) => setForm({ ...form, officer: e.target.value })} />
          <span className="mt-1 block text-xs text-ink-soft">Their share of Somosure&apos;s net commission on a financed policy.</span>
        </label>
        <label className="text-sm">
          <span className="font-medium text-ink">Somosure commission, % of premium</span>
          <input className={`${INPUT} mt-1`} type="number" min="0" max="100" step="0.01" placeholder="Not set" disabled={!canEdit || busy} value={form.basis} onChange={(e) => setForm({ ...form, basis: e.target.value })} />
          <span className="mt-1 block text-xs text-ink-soft">Optional. Leave empty to enter the real net commission for each policy yourself.</span>
        </label>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={save} disabled={!canEdit || busy}>
          {busy ? "Saving…" : "Save"}
        </Button>
        {message && <span className="text-sm text-status-success">{message}</span>}
        {error && <span className="text-sm text-status-error">{error}</span>}
      </div>
    </Card>
  );
}

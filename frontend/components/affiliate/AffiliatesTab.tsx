"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api, getTokenRole } from "@/lib/api";
import type { AffiliatePartner } from "@/lib/types";
import { CustomerPicker, Field, PickedCustomer, inputClass, kes } from "@/components/affiliate/shared";

const BASE = "/api/v1/admin/affiliate-program";

export function AffiliatesTab() {
  const canEdit = ["super_admin", "management"].includes(getTokenRole() ?? "");
  const [partners, setPartners] = useState<AffiliatePartner[]>([]);
  const [q, setQ] = useState("");
  const [person, setPerson] = useState<PickedCustomer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setPartners(await api.get<AffiliatePartner[]>(`${BASE}/partners${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ""}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load affiliates");
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function enroll() {
    if (!person) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`${BASE}/partners`, { customer_id: person.id }, { reason: `Enrolled ${person.full_name} as an affiliate` });
      setPerson(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not enrol");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(p: AffiliatePartner, status: "active" | "suspended") {
    const reason = window.prompt(status === "suspended" ? `Why pause ${p.customer_name}? (kept in the audit trail)` : `Reactivate ${p.customer_name}?`, "");
    if (reason === null) return;
    try {
      await api.patch(`${BASE}/partners/${p.id}`, { status }, { reason: reason || (status === "suspended" ? "Paused" : "Reactivated") });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm text-ink-soft">
        Anyone who refers someone can earn commission. Enrolling a customer as an affiliate gives them a personal link and code that
        works for everyone they share it with (ordinary referral codes are single-use), plus their own earnings page. Pausing an
        affiliate stops new commissions for them.
      </p>
      {error && <p className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      {canEdit && (
        <Card className="flex flex-wrap items-end gap-3">
          <div className="min-w-[18rem] flex-1"><Field label="Enrol a customer as an affiliate"><CustomerPicker value={person} onChange={setPerson} /></Field></div>
          <Button onClick={enroll} disabled={!person || busy}>{busy ? "Enrolling…" : "Enrol"}</Button>
        </Card>
      )}

      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} placeholder="Search name, phone or code" className={`${inputClass} max-w-xs`} />
        <Button variant="ghost" onClick={load}>Search</Button>
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="bg-neutral text-xs uppercase text-ink-soft">
            <tr><th className="px-4 py-3">Affiliate</th><th className="px-4 py-3">Code</th><th className="px-4 py-3">Referred</th><th className="px-4 py-3">Bought cover</th><th className="px-4 py-3 text-right">To pay</th><th className="px-4 py-3 text-right">Paid</th><th className="px-4 py-3"></th></tr>
          </thead>
          <tbody>
            {partners.map((p) => (
              <tr key={p.id} className="border-t border-neutral-border align-top">
                <td className="px-4 py-3">
                  <p className="font-medium text-ink">{p.customer_name} {p.status === "suspended" && <Badge tone="error">paused</Badge>}</p>
                  <p className="text-xs text-ink-soft">M-Pesa {p.payout_phone ?? p.customer_phone}</p>
                </td>
                <td className="px-4 py-3 font-mono text-xs">{p.code}</td>
                <td className="px-4 py-3">{p.referred}</td>
                <td className="px-4 py-3">{p.converted}</td>
                <td className="px-4 py-3 text-right">{kes(Number(p.earned_pending) + Number(p.earned_approved))}</td>
                <td className="px-4 py-3 text-right">{kes(p.earned_paid)}</td>
                <td className="px-4 py-3 text-xs font-semibold">
                  {canEdit && (p.status === "active"
                    ? <button type="button" onClick={() => setStatus(p, "suspended")} className="text-status-error hover:underline">Pause</button>
                    : <button type="button" onClick={() => setStatus(p, "active")} className="text-brand-deep hover:underline">Reactivate</button>)}
                </td>
              </tr>
            ))}
            {partners.length === 0 && <tr><td colSpan={7} className="px-4 py-10 text-center text-ink-soft">No affiliates enrolled yet.</td></tr>}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

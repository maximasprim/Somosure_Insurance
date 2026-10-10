"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { DiscountCredit, DiscountPage, DiscountStatus, EligibleApplication } from "@/lib/types";
import { CustomerPicker, Field, PickedCustomer, inputClass, kes } from "@/components/affiliate/shared";

const BASE = "/api/v1/admin/affiliate-program";
const PAGE = 25;
const TONE: Record<DiscountStatus, "success" | "error" | "brand" | "neutral" | "info"> = {
  available: "success",
  applied: "brand",
  expired: "neutral",
  cancelled: "error",
};
const FILTERS: { key: "" | DiscountStatus; label: string }[] = [
  { key: "available", label: "Available" },
  { key: "applied", label: "Applied" },
  { key: "expired", label: "Expired" },
  { key: "cancelled", label: "Cancelled" },
  { key: "", label: "All" },
];

type Open = { id: string; kind: "apply" | "release" | "cancel" } | null;

/** Discount credits owed to existing customers for referrals. Staff decide, case by case,
 *  which of the customer's applications each one is applied to. */
export function DiscountsTab() {
  const [status, setStatus] = useState<"" | DiscountStatus>("available");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<DiscountPage | null>(null);
  const [open, setOpen] = useState<Open>(null);
  const [apps, setApps] = useState<EligibleApplication[]>([]);
  const [chosen, setChosen] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showGrant, setShowGrant] = useState(false);

  const load = useCallback(
    async (next = 0) => {
      setError(null);
      try {
        const params = new URLSearchParams({ limit: String(PAGE), offset: String(next) });
        if (status) params.set("status", status);
        if (q.trim()) params.set("q", q.trim());
        setPage(await api.get<DiscountPage>(`${BASE}/discounts?${params}`));
        setOffset(next);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load discount credits");
      }
    },
    [status, q]
  );
  useEffect(() => {
    load(0);
  }, [load]);

  function close() {
    setOpen(null);
    setApps([]);
    setChosen("");
    setAmount("");
    setReason("");
  }

  async function startApply(credit: DiscountCredit) {
    setOpen({ id: credit.id, kind: "apply" });
    setChosen("");
    setAmount("");
    setReason("");
    setError(null);
    try {
      setApps(await api.get<EligibleApplication[]>(`${BASE}/discounts/${credit.id}/applications`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the customer's applications");
    }
  }

  async function submit(credit: DiscountCredit) {
    if (!open) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (open.kind === "apply") {
        await api.post(
          `${BASE}/discounts/${credit.id}/apply`,
          { application_id: chosen, amount: amount || undefined, reason },
          { reason }
        );
        setMessage("Discount applied. It will be taken off the customer's payment.");
      } else {
        await api.post(`${BASE}/discounts/${credit.id}/${open.kind}`, { reason }, { reason });
        setMessage(open.kind === "release" ? "Discount released back to the customer." : "Credit cancelled.");
      }
      close();
      await load(offset);
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work");
    } finally {
      setBusy(false);
    }
  }

  const items = page?.items ?? [];
  const total = page?.total ?? 0;
  const selectedApp = apps.find((a) => a.application_id === chosen);

  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm text-ink-soft">
        When an existing customer refers someone who buys insurance, they can earn a discount credit (set in Rates &amp; settings).
        A credit does nothing on its own: you choose which of the customer&apos;s applications it goes on, and the amount is taken off what they pay.
      </p>

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setStatus(f.key)}
            className={`rounded-full px-4 py-1.5 text-sm font-semibold ${status === f.key ? "bg-brand-deep text-white" : "bg-neutral text-ink-soft hover:text-ink"}`}
          >
            {f.label}
          </button>
        ))}
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load(0)} placeholder="Search customer name or phone" className={`${inputClass} ml-auto max-w-xs`} />
        <Button variant="ghost" onClick={() => setShowGrant((v) => !v)}>{showGrant ? "Close" : "Give a discount"}</Button>
      </div>

      {showGrant && <GrantForm onDone={() => { setShowGrant(false); setMessage("Discount credit given."); load(0); }} />}

      {message && <p className="rounded-control bg-status-success/10 px-4 py-2 text-sm text-status-success">{message}</p>}
      {error && <p className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="bg-neutral text-xs uppercase text-ink-soft">
            <tr><th className="px-3 py-3">Customer</th><th className="px-3 py-3">Credit</th><th className="px-3 py-3">Why</th><th className="px-3 py-3">Status</th><th className="px-3 py-3"></th></tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} className="border-t border-neutral-border align-top">
                <td className="px-3 py-3"><p className="font-medium text-ink">{c.customer_name}</p><p className="text-xs text-ink-soft">{c.customer_phone}</p></td>
                <td className="px-3 py-3">
                  <p className="font-semibold text-ink">{c.description}</p>
                  <p className="text-xs text-ink-soft">{c.expires_at ? `Expires ${new Date(c.expires_at).toLocaleDateString()}` : "No expiry"}</p>
                </td>
                <td className="max-w-xs px-3 py-3 text-xs text-ink-soft">{c.note}{c.status_note && <p className="mt-1">“{c.status_note}”</p>}</td>
                <td className="px-3 py-3">
                  <Badge tone={TONE[c.status]}>{c.status}</Badge>
                  {c.status === "applied" && <p className="mt-1 text-xs text-ink-soft">{kes(c.applied_amount)} off {c.applied_application_reference}</p>}
                </td>
                <td className="px-3 py-3">
                  {open?.id === c.id ? (
                    <div className="flex min-w-[18rem] flex-col gap-2">
                      {open.kind === "apply" && (
                        <>
                          <select value={chosen} onChange={(e) => { setChosen(e.target.value); setAmount(""); }} className={inputClass}>
                            <option value="">Choose the application…</option>
                            {apps.map((a) => (
                              <option key={a.application_id} value={a.application_id} disabled={!a.eligible}>
                                {a.reference} · {kes(a.total)}{a.eligible ? ` · up to ${kes(a.max_discount)} off` : ` · ${a.blocked_reason ?? "not available"}`}
                              </option>
                            ))}
                          </select>
                          {selectedApp && (
                            <div className="flex items-center gap-2 text-xs text-ink-soft">
                              Take off
                              <input type="number" min="0.01" step="0.01" max={selectedApp.max_discount} placeholder={selectedApp.max_discount} value={amount} onChange={(e) => setAmount(e.target.value)} className={`${inputClass} max-w-[7rem]`} />
                              KES (blank = the full {kes(selectedApp.max_discount)})
                            </div>
                          )}
                        </>
                      )}
                      <input autoFocus value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (required)" className={inputClass} />
                      <div className="flex gap-2">
                        <Button size="md" disabled={busy || reason.trim().length < 3 || (open.kind === "apply" && !chosen)} onClick={() => submit(c)}>
                          {open.kind === "apply" ? "Apply discount" : open.kind === "release" ? "Release" : "Cancel credit"}
                        </Button>
                        <Button size="md" variant="ghost" onClick={close}>Back</Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-start gap-1 text-xs font-semibold">
                      {c.status === "available" && <button type="button" onClick={() => startApply(c)} className="text-brand-deep hover:underline">Apply to an application…</button>}
                      {c.status === "available" && <button type="button" onClick={() => { setOpen({ id: c.id, kind: "cancel" }); setReason(""); }} className="text-status-error hover:underline">Cancel…</button>}
                      {c.status === "applied" && <button type="button" onClick={() => { setOpen({ id: c.id, kind: "release" }); setReason(""); }} className="text-status-error hover:underline">Release…</button>}
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {page && items.length === 0 && <tr><td colSpan={5} className="px-4 py-10 text-center text-ink-soft">No discount credits here yet.</td></tr>}
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

function GrantForm({ onDone }: { onDone: () => void }) {
  const [person, setPerson] = useState<PickedCustomer | null>(null);
  const [type, setType] = useState<"percent" | "fixed">("percent");
  const [value, setValue] = useState("");
  const [days, setDays] = useState("365");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function grant() {
    if (!person) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`${BASE}/discounts`, { customer_id: person.id, discount_type: type, discount_value: value, valid_days: Number(days) || null, reason }, { reason });
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not give the discount");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-col gap-4">
      <p className="text-sm font-semibold">Give a customer a discount credit directly</p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Customer"><CustomerPicker value={person} onChange={setPerson} /></Field>
        <Field label="Discount">
          <div className="flex gap-2">
            <select value={type} onChange={(e) => setType(e.target.value as "percent" | "fixed")} className={`${inputClass} max-w-[8rem]`}>
              <option value="percent">% off</option>
              <option value="fixed">KES off</option>
            </select>
            <input type="number" min="0" step="0.01" value={value} onChange={(e) => setValue(e.target.value)} className={`${inputClass} max-w-[7rem]`} />
          </div>
        </Field>
        <Field label="Usable for (days)"><input type="number" min="1" value={days} onChange={(e) => setDays(e.target.value)} className={inputClass} /></Field>
        <Field label="Reason (required)"><input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Apology for a delayed claim" className={inputClass} /></Field>
      </div>
      {error && <p className="text-sm text-status-error">{error}</p>}
      <div><Button onClick={grant} disabled={busy || !person || !value || reason.trim().length < 3}>{busy ? "Saving…" : "Give discount"}</Button></div>
    </Card>
  );
}

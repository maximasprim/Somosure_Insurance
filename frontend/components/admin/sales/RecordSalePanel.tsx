"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import { dmy, kes } from "@/lib/salesImport";
import { POST_FLAG_LABELS } from "@/lib/salesImport";
import { type CustomerHit, type RecentSale, type RecordOptions, type RecordResult, SALES_BASE } from "@/lib/salesSync";

const today = () => new Date().toISOString().slice(0, 10);

/** One year after the start, less a day: 2026-01-06 -> 2027-01-05, as the sheet does it. */
function defaultExpiry(start: string): string {
  if (!start) return "";
  const d = new Date(`${start}T00:00:00`);
  d.setFullYear(d.getFullYear() + 1);
  d.setDate(d.getDate() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const EMPTY = {
  client_name: "", phone: "", provider_id: "", new_underwriter: "", reg_or_product: "", start_date: today(), expiry_date: "", date_paid: today(),
  staff_name: "", branch: "", business_type: "", policy_number: "", cover_type: "", premium: "", commission: "", wht: "",
};

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-ink">{label}</label>
      {children}
      {hint && <span className="text-xs text-ink-soft">{hint}</span>}
    </div>
  );
}

const selectClass = "rounded-control border border-neutral-border bg-white px-3 py-2 text-sm";

export function RecordSalePanel({ onRecorded }: { onRecorded: () => void }) {
  const [options, setOptions] = useState<RecordOptions | null>(null);
  const [f, setF] = useState(EMPTY);
  const [expiryTouched, setExpiryTouched] = useState(false);
  const [commissionTouched, setCommissionTouched] = useState(false);
  const [hits, setHits] = useState<CustomerHit[]>([]);
  const [customer, setCustomer] = useState<CustomerHit | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicates, setDuplicates] = useState<RecordResult["duplicates"] | null>(null);
  const [result, setResult] = useState<RecordResult | null>(null);
  const [recent, setRecent] = useState<RecentSale[]>([]);
  const [recentLoaded, setRecentLoaded] = useState(false);
  const lookup = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadRecent = useCallback(async () => {
    try {
      setRecent(await api.get<RecentSale[]>(`${SALES_BASE}/record/recent`));
    } catch {
      /* the list is a convenience */
    } finally {
      setRecentLoaded(true);
    }
  }, []);

  useEffect(() => {
    api
      .get<RecordOptions>(`${SALES_BASE}/record/options`)
      .then(setOptions)
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Could not load");
        setOptions({ providers: [], staff: [], branches: [], product_hints: [], wht_rate: "0.10" });
      });
    loadRecent();
  }, [loadRecent]);

  const provider = options?.providers.find((p) => p.id === f.provider_id) ?? null;
  const rate = provider?.typical_commission_rate ? Number(provider.typical_commission_rate) : null;
  const premium = Number(f.premium) || 0;
  const commission = f.commission !== "" ? Number(f.commission) : null;
  const wht = f.wht !== "" ? Number(f.wht) : commission !== null && options ? Math.round(commission * Number(options.wht_rate) * 100) / 100 : null;
  const net = commission !== null && wht !== null ? Math.round((commission - wht) * 100) / 100 : null;

  const set = (key: keyof typeof EMPTY) => (value: string) => setF((prev) => ({ ...prev, [key]: value }));

  // Fill in what the sheet works out, until the person types their own figure.
  useEffect(() => {
    if (!expiryTouched) setF((prev) => ({ ...prev, expiry_date: defaultExpiry(prev.start_date) }));
  }, [f.start_date, expiryTouched]);
  useEffect(() => {
    if (!commissionTouched && rate && premium > 0) setF((prev) => ({ ...prev, commission: String(Math.round(premium * rate * 100) / 100) }));
  }, [premium, rate, commissionTouched]);

  // Suggest customers who are already in the system, so the same person is not entered twice.
  useEffect(() => {
    if (customer) return;
    const q = f.phone.trim().length >= 6 ? f.phone.trim() : f.client_name.trim();
    if (lookup.current) clearTimeout(lookup.current);
    if (q.length < 3) {
      setHits([]);
      return;
    }
    lookup.current = setTimeout(() => {
      api
        .get<{ customers: CustomerHit[] }>(`/api/v1/admin/search?q=${encodeURIComponent(q)}`)
        .then((r) => setHits((r.customers ?? []).slice(0, 5)))
        .catch(() => setHits([]));
    }, 350);
  }, [f.client_name, f.phone, customer]);

  const missing = useMemo(() => {
    const m: string[] = [];
    if (!f.client_name.trim()) m.push("client name");
    if (!f.provider_id && !f.new_underwriter.trim()) m.push("insurer");
    if (!f.reg_or_product.trim()) m.push("registration or product");
    if (!f.start_date) m.push("start date");
    if (!f.date_paid) m.push("date paid");
    if (!(premium > 0)) m.push("premium");
    return m;
  }, [f, premium]);

  async function submit(confirmDuplicate: boolean) {
    setBusy(true);
    setError(null);
    setDuplicates(null);
    try {
      const body = {
        client_name: f.client_name, phone: f.phone || null, customer_id: customer?.id ?? null,
        provider_id: f.provider_id === "new" ? null : f.provider_id || null, new_underwriter: f.provider_id === "new" ? f.new_underwriter : null,
        reg_or_product: f.reg_or_product, start_date: f.start_date, expiry_date: f.expiry_date || null, date_paid: f.date_paid,
        staff_name: f.staff_name || null, branch: f.branch || null, business_type: f.business_type || null, policy_number: f.policy_number || null,
        cover_type: f.cover_type || null, premium: premium, commission: commission, wht: f.wht !== "" ? Number(f.wht) : null,
        confirm_duplicate: confirmDuplicate,
      };
      const r = await api.post<RecordResult>(`${SALES_BASE}/record`, body);
      if (!r.created) {
        setDuplicates(r.duplicates ?? []);
      } else {
        setResult(r);
        onRecorded();
        loadRecent();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record the sale");
    } finally {
      setBusy(false);
    }
  }

  function again() {
    setResult(null);
    setF({ ...EMPTY, start_date: today(), date_paid: today(), staff_name: f.staff_name, branch: f.branch });
    setExpiryTouched(false);
    setCommissionTouched(false);
    setCustomer(null);
    setHits([]);
  }

  async function voidSale(id: string) {
    if (!window.confirm("Void this sale? It removes the policy, payment and quote created for it. Use this only for a sale recorded by mistake.")) return;
    try {
      await api.del(`${SALES_BASE}/record/${id}`);
      loadRecent();
      onRecorded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not void");
    }
  }

  // The form, its drop-downs and the recent list appear together.
  if (!options || !recentLoaded) return <TabSkeleton />;

  if (result) {
    return (
      <div className="flex flex-col gap-4">
        <Card className="p-5">
          <p className="rounded-control bg-status-success/10 px-4 py-2 text-sm text-status-success">
            Recorded. Policy <strong>{result.policy_number}</strong> now exists in the system, with its payment, and counts in sales, reports and renewals.
            {result.customer_existed ? " It was added to the existing customer." : " A new customer was created."}
          </p>
          {result.flags && result.flags.length > 0 && (
            <div className="mt-3 text-sm">
              <p className="font-medium">To review later:</p>
              <ul className="mt-1 list-disc pl-5 text-xs text-ink-soft">
                {result.flags.map((fl) => <li key={fl.code}>{POST_FLAG_LABELS[fl.code] ?? fl.message}</li>)}
              </ul>
            </div>
          )}
          <div className="mt-4 flex flex-wrap gap-3">
            <Button onClick={again}>Record another</Button>
            {result.customer_id && <a className="self-center text-sm text-brand-deep underline" href={`/admin/customers/${result.customer_id}`}>Open the customer</a>}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-5">
        <h2 className="text-lg font-semibold">Record a sale</h2>
        <p className="mt-1 text-sm text-ink-soft">
          The same details you put on a row of the weekly sheet. It is saved as a real policy with its payment, counts in sales, reports and renewals straight away,
          and appears in the weekly report the system exports. If the same sale is also typed in the sheet later, the import recognises it and merges the two.
          Only the fields marked * are needed; anything left out is flagged for review.
        </p>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <Input label="Client name *" value={f.client_name} onChange={(e) => { set("client_name")(e.target.value); if (customer) setCustomer(null); }} />
          <Input label="Phone" value={f.phone} onChange={(e) => { set("phone")(e.target.value); if (customer) setCustomer(null); }} placeholder="0712 345 678" />
          <Field label="Insurer *">
            <select className={selectClass} value={f.provider_id} onChange={(e) => { set("provider_id")(e.target.value); setCommissionTouched(false); }}>
              <option value="">Choose…</option>
              {options?.providers.map((p) => <option key={p.id} value={p.id}>{p.name}{p.status !== "active" ? " (not on the platform)" : ""}</option>)}
              <option value="new">+ Add a new insurer…</option>
            </select>
            {f.provider_id === "new" && <Input label="" aria-label="New insurer" placeholder="Insurer name" value={f.new_underwriter} onChange={(e) => set("new_underwriter")(e.target.value)} />}
          </Field>

          {(customer || hits.length > 0) && (
            <div className="rounded-control bg-neutral/60 p-3 text-sm md:col-span-3">
              {customer ? (
                <p>
                  Using existing customer <strong>{customer.full_name}</strong> {customer.phone ? `(${customer.phone})` : ""}.{" "}
                  <button className="text-brand-deep underline" onClick={() => setCustomer(null)}>Not them</button>
                </p>
              ) : (
                <>
                  <p className="text-xs text-ink-soft">Already a customer? Pick them so the sale goes on their record:</p>
                  <ul className="mt-1 flex flex-wrap gap-2">
                    {hits.map((h) => (
                      <li key={h.id}>
                        <button className="rounded-full border border-neutral-border bg-white px-3 py-1 text-xs hover:bg-brand-tint" onClick={() => { setCustomer(h); setHits([]); }}>
                          {h.full_name}{h.phone ? ` · ${h.phone}` : ""}
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}

          <div>
            <Input label="Registration or product *" list="product-hints" value={f.reg_or_product} onChange={(e) => set("reg_or_product")(e.target.value)} placeholder="KDR 904V, or PI, WIBA, MEDICAL…" />
            <datalist id="product-hints">{options?.product_hints.map((h) => <option key={h} value={h} />)}</datalist>
          </div>
          <Input label="Start date *" type="date" value={f.start_date} onChange={(e) => { set("start_date")(e.target.value); }} />
          <Input label="Expiry date" type="date" value={f.expiry_date} onChange={(e) => { setExpiryTouched(true); set("expiry_date")(e.target.value); }} />
          <Input label="Date paid *" type="date" value={f.date_paid} onChange={(e) => set("date_paid")(e.target.value)} />
          <div>
            <Input label="Staff" list="staff-hints" value={f.staff_name} onChange={(e) => set("staff_name")(e.target.value)} />
            <datalist id="staff-hints">{options?.staff.map((s) => <option key={s} value={s} />)}</datalist>
          </div>
          <div>
            <Input label="Branch" list="branch-hints" value={f.branch} onChange={(e) => set("branch")(e.target.value)} />
            <datalist id="branch-hints">{options?.branches.map((b) => <option key={b} value={b} />)}</datalist>
          </div>
          <Field label="New business / renewal">
            <select className={selectClass} value={f.business_type} onChange={(e) => set("business_type")(e.target.value)}>
              <option value="">Not stated</option>
              <option value="new_business">New business</option>
              <option value="renewal">Renewal</option>
            </select>
          </Field>
          <Input label="Policy number" value={f.policy_number} onChange={(e) => set("policy_number")(e.target.value)} placeholder="The insurer's number" />
          <Input label="Cover type" value={f.cover_type} onChange={(e) => set("cover_type")(e.target.value)} placeholder="COMP, TPO…" />
          <Input label="Premium paid (KES) *" type="number" min="0" value={f.premium} onChange={(e) => set("premium")(e.target.value)} />
          <Field label="Gross commission (KES)" hint={rate ? `Filled in at ${(rate * 100).toFixed(1)}% - ${provider?.underwriter}'s usual rate. Change it if this policy differs.` : "Type the commission, or leave empty."}>
            <input className={selectClass} type="number" min="0" value={f.commission} onChange={(e) => { setCommissionTouched(true); set("commission")(e.target.value); }} />
          </Field>
          <Field label="Withholding tax / net revenue" hint="Worked out from the commission, as in the sheet.">
            <div className="rounded-control bg-neutral/60 px-3 py-2 text-sm">
              {wht !== null ? `Tax ${kes(wht)} · Net ${kes(net)}` : "-"}
            </div>
          </Field>
        </div>

        {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}
        {duplicates && (
          <div className="mt-4 rounded-control border border-status-error/40 p-4 text-sm">
            <p className="font-semibold">This looks like a sale that is already recorded</p>
            <ul className="mt-1 list-disc pl-5 text-xs">{duplicates.map((d, i) => <li key={i}>{d.where}: {d.what}</li>)}</ul>
            <div className="mt-3 flex gap-2">
              <Button onClick={() => submit(true)} disabled={busy}>It is a different sale - record it</Button>
              <Button variant="ghost" onClick={() => setDuplicates(null)}>Cancel</Button>
            </div>
          </div>
        )}
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button onClick={() => submit(false)} disabled={busy || missing.length > 0}>{busy ? "Recording…" : "Record the sale"}</Button>
          {missing.length > 0 && <span className="text-xs text-ink-soft">Still needed: {missing.join(", ")}</span>}
        </div>
      </Card>

      {recent.length > 0 && (
        <Card className="p-5">
          <h3 className="text-sm font-semibold">Recently recorded in the system</h3>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-ink-soft"><tr><th className="py-1 pr-3">Paid</th><th className="pr-3">Client</th><th className="pr-3">Insurer</th><th className="pr-3">Policy no.</th><th className="pr-3 text-right">Premium</th><th className="pr-3">Staff · branch</th><th /></tr></thead>
              <tbody>
                {recent.map((r) => (
                  <tr key={r.id} className="border-t border-neutral-border">
                    <td className="py-1.5 pr-3 whitespace-nowrap">{dmy(r.date_paid)}</td>
                    <td className="pr-3 font-medium">{r.client_name} {r.post_flags && r.post_flags.length > 0 && <Badge tone="brand">review</Badge>}</td>
                    <td className="pr-3">{r.underwriter ?? "-"}</td>
                    <td className="pr-3 font-mono">{r.policy_number ?? "-"}</td>
                    <td className="pr-3 text-right">{kes(r.premium)}</td>
                    <td className="pr-3">{[r.staff_name, r.branch].filter(Boolean).join(" · ") || "-"}</td>
                    <td className="whitespace-nowrap">
                      {r.customer_id && <a className="mr-3 text-brand-deep underline" href={`/admin/customers/${r.customer_id}`}>Customer</a>}
                      <button className="text-status-error underline" onClick={() => voidSale(r.id)}>Void</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

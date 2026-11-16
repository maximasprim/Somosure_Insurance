"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import { dmy, kes, MONTHS, PRODUCT_LABELS } from "@/lib/salesImport";
import { SALES_BASE, SOURCE_LABELS, type SalesOptions, type UnifiedSale, type UnifiedSalesPage } from "@/lib/salesSync";

const PAGE = 50;

function Select({ label, value, onChange, children }: { label: string; value: string; onChange: (v: string) => void; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-ink">{label}</label>
      <select className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={value} onChange={(e) => onChange(e.target.value)}>
        {children}
      </select>
    </div>
  );
}

export function AllSalesPanel({ refreshKey = 0 }: { refreshKey?: number }) {
  const [options, setOptions] = useState<SalesOptions | null>(null);
  const [f, setF] = useState({ source: "", year: "", month: "", underwriter: "", staff: "", branch: "", product: "", business_type: "", q: "" });
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<UnifiedSalesPage | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof typeof f) => (value: string) => {
    setF((prev) => ({ ...prev, [key]: value }));
    setOffset(0);
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
      Object.entries(f).forEach(([k, v]) => v && params.set(k, v));
      setPage(await api.get<UnifiedSalesPage>(`${SALES_BASE}?${params.toString()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load sales");
    } finally {
      setLoading(false);
    }
  }, [f, offset]);

  useEffect(() => {
    api.get<SalesOptions>(`${SALES_BASE}/options`).then(setOptions).catch(() => setOptions({ years: [], underwriters: [], staff: [], branches: [], products: [] }));
  }, [refreshKey]);
  useEffect(() => {
    load();
  }, [load, refreshKey]);

  // Nothing is drawn until the filter lists AND the first page of sales have both arrived.
  if (!options || (!page && !error)) return <TabSkeleton />;

  const total = page?.total ?? 0;

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <p className="mb-3 text-xs text-ink-soft">
          Every sale in one list: sold through the platform, or recorded in the weekly report workbook. A sale is counted once - a workbook row stands in for the
          platform policy it matches. Demo policies are left out. The date is the date paid.
        </p>
        <div className="grid gap-3 md:grid-cols-4 lg:grid-cols-5">
          <Select label="Where it came from" value={f.source} onChange={set("source")}>
            <option value="">Both</option>
            <option value="platform">Platform</option>
            <option value="workbook">Workbook</option>
            <option value="manual">Entered in system</option>
          </Select>
          <Select label="Year" value={f.year} onChange={set("year")}>
            <option value="">All</option>
            {options?.years.map((y) => <option key={y} value={y}>{y}</option>)}
          </Select>
          <Select label="Month" value={f.month} onChange={set("month")}>
            <option value="">All</option>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </Select>
          <Select label="Underwriter" value={f.underwriter} onChange={set("underwriter")}>
            <option value="">All</option>
            {options?.underwriters.map((u) => <option key={u} value={u}>{u}</option>)}
          </Select>
          <Select label="Staff" value={f.staff} onChange={set("staff")}>
            <option value="">All</option>
            {options?.staff.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
          <Select label="Branch" value={f.branch} onChange={set("branch")}>
            <option value="">All</option>
            {options?.branches.map((b) => <option key={b} value={b}>{b}</option>)}
          </Select>
          <Select label="Product" value={f.product} onChange={set("product")}>
            <option value="">All</option>
            {options?.products.map((p) => <option key={p} value={p}>{PRODUCT_LABELS[p] ?? p}</option>)}
          </Select>
          <Select label="New / renewal" value={f.business_type} onChange={set("business_type")}>
            <option value="">All</option>
            <option value="new_business">New business</option>
            <option value="renewal">Renewal</option>
          </Select>
          <div className="md:col-span-2">
            <Input label="Search client, policy number, registration, phone" value={f.q} onChange={(e) => set("q")(e.target.value)} />
          </div>
        </div>
      </Card>

      {error && <p className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
          <span>
            <strong>{total}</strong> sales · premium <strong>KES {kes(page?.premium)}</strong> · commission <strong>KES {kes(page?.commission)}</strong>
          </span>
          <span className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => setOffset(Math.max(0, offset - PAGE))} disabled={offset === 0 || loading}>Previous</Button>
            <span className="text-xs text-ink-soft">{total ? `${offset + 1}-${Math.min(offset + PAGE, total)}` : "0"}</span>
            <Button variant="ghost" onClick={() => setOffset(offset + PAGE)} disabled={offset + PAGE >= total || loading}>Next</Button>
          </span>
        </div>
        {loading && !page ? (
          <p className="text-ink-soft">Loading…</p>
        ) : total === 0 ? (
          <p className="text-ink-soft">No sales match. Import the weekly report on the Sales import page, or sell through the platform.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-ink-soft">
                <tr>
                  <th className="py-1 pr-3">Paid</th><th className="pr-3">Client</th><th className="pr-3">Reg / product</th><th className="pr-3">Underwriter</th>
                  <th className="pr-3">Policy no.</th><th className="pr-3 text-right">Premium</th><th className="pr-3 text-right">Commission</th>
                  <th className="pr-3">Staff · branch</th><th>From</th>
                </tr>
              </thead>
              <tbody>
                {page?.items.map((s: UnifiedSale) => (
                  <Fragment key={`${s.source}-${s.id}`}>
                    <tr className="cursor-pointer border-t border-neutral-border hover:bg-neutral/50" onClick={() => setOpen(open === s.id ? null : s.id)}>
                      <td className="py-1.5 pr-3 whitespace-nowrap">{dmy(s.sold_on)}</td>
                      <td className="pr-3 font-medium">{s.client_name ?? "-"}</td>
                      <td className="pr-3">{s.reg_no ?? PRODUCT_LABELS[s.product ?? ""] ?? "-"}</td>
                      <td className="pr-3">{s.underwriter ?? "-"}</td>
                      <td className="pr-3 font-mono">{s.policy_number ?? "-"}</td>
                      <td className="pr-3 text-right">{kes(s.premium)}</td>
                      <td className="pr-3 text-right">{kes(s.commission)}</td>
                      <td className="pr-3">{[s.staff, s.branch].filter(Boolean).join(" · ") || "-"}</td>
                      <td className="whitespace-nowrap">
                        <Badge tone={s.source === "platform" ? "info" : "neutral"}>{SOURCE_LABELS[s.source] ?? s.source}</Badge>
                      </td>
                    </tr>
                    {open === s.id && (
                      <tr className="bg-neutral/40">
                        <td colSpan={9} className="px-3 py-3">
                          <div className="grid gap-x-8 gap-y-1 md:grid-cols-4">
                            <span>Start: <strong>{dmy(s.start_date)}</strong></span>
                            <span>Expiry: <strong>{dmy(s.expiry_date)}</strong></span>
                            <span>Phone: <strong>{s.phone ?? "-"}</strong></span>
                            <span>Business: <strong>{s.business_type === "new_business" ? "New business" : s.business_type === "renewal" ? "Renewal" : "-"}</strong></span>
                            <span>Withholding tax: <strong>{kes(s.wht)}</strong></span>
                            <span>Net revenue: <strong>{kes(s.net_revenue)}</strong></span>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-4">
                            {s.customer_id ? (
                              <a className="text-brand-deep underline" href={`/admin/customers/${s.customer_id}`}>Open customer</a>
                            ) : (
                              <span className="text-ink-soft">Not linked to a customer yet (Customers tab)</span>
                            )}
                            {s.source === "platform" && s.policy_number && (
                              <a className="text-brand-deep underline" href={`/admin/policies?search=${encodeURIComponent(s.policy_number)}`}>Open policy</a>
                            )}
                            {s.source === "platform+workbook" && s.policy_number && (
                              <a className="text-brand-deep underline" href={`/admin/policies?search=${encodeURIComponent(s.policy_number)}`}>Also a platform policy</a>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

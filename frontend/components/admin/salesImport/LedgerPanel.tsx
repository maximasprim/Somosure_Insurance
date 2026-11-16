"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import { BASE, dmy, type EntryOptions, type EntryPage, kes, MONTHS, PRODUCT_LABELS, type SalesEntry } from "@/lib/salesImport";

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

export function LedgerPanel({ refreshKey }: { refreshKey: number }) {
  const [options, setOptions] = useState<EntryOptions | null>(null);
  const [f, setF] = useState({ year: "", month: "", underwriter: "", staff: "", branch: "", product: "", level: "", status: "", q: "" });
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<EntryPage | null>(null);
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
      setPage(await api.get<EntryPage>(`${BASE}/entries?${params.toString()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the ledger");
    } finally {
      setLoading(false);
    }
  }, [f, offset]);

  useEffect(() => {
    api.get<EntryOptions>(`${BASE}/entries/options`).then(setOptions).catch(() => setOptions({ years: [], underwriters: [], staff: [], branches: [], products: [] }));
  }, [refreshKey]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  // Nothing is drawn until the filter lists AND the first page of rows have both arrived.
  if (!options || (!page && !error)) return <TabSkeleton />;

  const total = page?.total ?? 0;

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <div className="grid gap-3 md:grid-cols-4 lg:grid-cols-5">
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
          <Select label="Show" value={f.level} onChange={set("level")}>
            <option value="">Every row</option>
            <option value="issues">Rows with problems</option>
            <option value="error">Errors only</option>
          </Select>
          <Select label="Sheet status" value={f.status} onChange={set("status")}>
            <option value="">Any</option>
            <option value="active">In the sheet</option>
            <option value="missing_from_sheet">Not in the sheet</option>
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
            <strong>{total}</strong> rows · premium <strong>KES {kes(page?.premium)}</strong> · commission <strong>KES {kes(page?.commission)}</strong>
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
          <p className="text-ink-soft">Nothing here yet. Import a workbook on the Import tab.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-ink-soft">
                <tr>
                  <th className="py-1 pr-3">Month</th>
                  <th className="pr-3">Client</th>
                  <th className="pr-3">Reg / product</th>
                  <th className="pr-3">Underwriter</th>
                  <th className="pr-3">Policy no.</th>
                  <th className="pr-3 text-right">Premium</th>
                  <th className="pr-3 text-right">Commission</th>
                  <th className="pr-3">Staff · branch</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {page?.items.map((e: SalesEntry) => (
                  <Fragment key={e.id}>
                    <tr className="cursor-pointer border-t border-neutral-border hover:bg-neutral/50" onClick={() => setOpen(open === e.id ? null : e.id)}>
                      <td className="py-1.5 pr-3 whitespace-nowrap">{e.period_month ? MONTHS[e.period_month - 1].slice(0, 3) : "-"} {e.period_year}</td>
                      <td className="pr-3 font-medium">{e.client_name}</td>
                      <td className="pr-3">{e.reg_no ?? e.asset_ref ?? PRODUCT_LABELS[e.product_line] ?? "-"}</td>
                      <td className="pr-3">{e.underwriter ?? "-"}</td>
                      <td className="pr-3 font-mono">{e.policy_number ?? "-"}</td>
                      <td className="pr-3 text-right">{kes(e.premium)}</td>
                      <td className="pr-3 text-right">{kes(e.commission)}</td>
                      <td className="pr-3">{[e.staff_name, e.branch].filter(Boolean).join(" · ") || "-"}</td>
                      <td className="whitespace-nowrap">
                        {e.status === "missing_from_sheet" && <Badge tone="error">Not in sheet</Badge>}{" "}
                        {e.issue_level === "error" && <Badge tone="error">Error</Badge>}
                        {e.issue_level === "warning" && <Badge tone="brand">Check</Badge>}
                        {e.policy_id && <Badge tone="info">On platform</Badge>}
                      </td>
                    </tr>
                    {open === e.id && (
                      <tr className="bg-neutral/40">
                        <td colSpan={9} className="px-3 py-3">
                          <div className="grid gap-x-8 gap-y-1 md:grid-cols-3">
                            <span>Start: <strong>{dmy(e.start_date)}</strong></span>
                            <span>Expiry: <strong>{dmy(e.expiry_date)}</strong></span>
                            <span>Paid: <strong>{dmy(e.date_paid)}</strong></span>
                            <span>Business: <strong>{e.business_type === "new_business" ? "New business" : e.business_type === "renewal" ? "Renewal" : "-"}</strong></span>
                            <span>Cover: <strong>{e.cover_type ?? "-"}</strong></span>
                            <span>Phone: <strong>{e.phone ?? "-"}</strong></span>
                            <span>Withholding tax: <strong>{kes(e.wht)}</strong></span>
                            <span>Net revenue: <strong>{kes(e.net_revenue)}</strong></span>
                            <span>Sheet: <strong>{e.sheet_name} row {e.sheet_row ?? "?"}</strong></span>
                          </div>
                          {e.flags && e.flags.length > 0 && (
                            <ul className="mt-2 flex flex-col gap-1">
                              {e.flags.map((fl, i) => (
                                <li key={i} className="flex gap-2">
                                  <Badge tone={fl.severity === "error" ? "error" : fl.severity === "warning" ? "brand" : "neutral"}>{fl.severity}</Badge>
                                  <span className="text-ink-soft">{fl.message}</span>
                                </li>
                              ))}
                            </ul>
                          )}
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

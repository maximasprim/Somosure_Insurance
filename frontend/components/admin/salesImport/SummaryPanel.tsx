"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { api } from "@/lib/api";
import { BASE, dmy, type EntryOptions, type GroupRow, kes, monthLabel, PRODUCT_LABELS, type Summary } from "@/lib/salesImport";

function Bars({ title, rows, labelKey, format }: { title: string; rows: GroupRow[]; labelKey: string; format?: (v: string) => string }) {
  const max = Math.max(1, ...rows.map((r) => Number(r.premium)));
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      <ul className="mt-3 flex flex-col gap-2 text-xs">
        {rows.length === 0 && <li className="text-ink-soft">No data.</li>}
        {rows.map((r, i) => {
          const raw = r[labelKey];
          const label = raw ? (format ? format(String(raw)) : String(raw)) : "Not stated";
          return (
            <li key={`${label}-${i}`}>
              <div className="flex justify-between gap-3">
                <span className="font-medium">{label}</span>
                <span className="text-ink-soft">
                  {r.count} policies · KES {kes(r.premium)} premium · KES {kes(r.commission)} commission
                </span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-neutral">
                <div className="h-1.5 rounded-full bg-brand-deep" style={{ width: `${Math.max(2, (Number(r.premium) / max) * 100)}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

export function SummaryPanel({ refreshKey }: { refreshKey: number }) {
  const [years, setYears] = useState<number[]>([]);
  const [year, setYear] = useState<number | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [optionsLoaded, setOptionsLoaded] = useState(false);

  useEffect(() => {
    api
      .get<EntryOptions>(`${BASE}/entries/options`)
      .then((o) => {
        setYears(o.years);
        setYear((current) => current ?? o.years[0] ?? null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load"))
      .finally(() => setOptionsLoaded(true));
  }, [refreshKey]);

  useEffect(() => {
    if (year === null) return;
    setError(null);
    api.get<Summary>(`${BASE}/summary?year=${year}`).then(setSummary).catch((e) => setError(e instanceof Error ? e.message : "Could not load the summary"));
  }, [year, refreshKey]);

  // The years list and the first year's figures are drawn together, never one before the other.
  if (!optionsLoaded || (years.length > 0 && !summary && !error)) return <TabSkeleton />;

  if (years.length === 0) return <p className="text-ink-soft">Nothing to summarise yet. Import a workbook on the Import tab.</p>;

  const monthlyMax = Math.max(1, ...(summary?.monthly.map((m) => Number(m.premium)) ?? [1]));
  const totalPremium = summary?.monthly.reduce((s, m) => s + Number(m.premium), 0) ?? 0;
  const totalCommission = summary?.monthly.reduce((s, m) => s + Number(m.commission), 0) ?? 0;
  const totalCount = summary?.monthly.reduce((s, m) => s + m.count, 0) ?? 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm font-medium">Year</label>
        <select className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={year ?? ""} onChange={(e) => setYear(Number(e.target.value))}>
          {years.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <span className="text-sm text-ink-soft">
          {totalCount} policies · KES {kes(totalPremium)} premium · KES {kes(totalCommission)} commission (rows in the sheet only)
        </span>
      </div>
      {error && <p className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      {summary && (
        <>
          <Card className="p-4">
            <h3 className="text-sm font-semibold">Month by month</h3>
            <ul className="mt-3 flex flex-col gap-2 text-xs">
              {summary.monthly.map((m) => (
                <li key={`${m.year}-${m.month}`} className="grid grid-cols-[110px_1fr] items-center gap-3">
                  <span className="font-medium">{monthLabel(m.month)} {m.year}</span>
                  <div>
                    <div className="h-2 rounded-full bg-neutral">
                      <div className="h-2 rounded-full bg-brand-deep" style={{ width: `${Math.max(2, (Number(m.premium) / monthlyMax) * 100)}%` }} />
                    </div>
                    <div className="mt-0.5 text-ink-soft">{m.count} policies · KES {kes(m.premium)} premium · KES {kes(m.commission)} commission</div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Bars title="By underwriter" rows={summary.by_underwriter} labelKey="underwriter" />
            <Bars title="By branch" rows={summary.by_branch} labelKey="branch" />
            <Bars title="By staff" rows={summary.by_staff} labelKey="staff" />
            <Bars
              title="New business and renewals"
              rows={summary.by_business_type}
              labelKey="business_type"
              format={(v) => (v === "new_business" ? "New business" : v === "renewal" ? "Renewal" : v)}
            />
            <Bars title="By product" rows={summary.by_product} labelKey="product" format={(v) => PRODUCT_LABELS[v] ?? v} />
          </div>

          <Card className="p-4">
            <h3 className="text-sm font-semibold">Expiring in the next {summary.expiring_window_days} days, not yet renewed</h3>
            <p className="text-xs text-ink-soft">From the expiry dates in the sheet. A policy is treated as renewed when the same registration has a later policy.</p>
            {summary.expiring.length === 0 ? (
              <p className="mt-3 text-sm text-ink-soft">None.</p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-ink-soft">
                    <tr><th className="py-1 pr-3">Expires</th><th className="pr-3">Client</th><th className="pr-3">Phone</th><th className="pr-3">Reg / product</th><th className="pr-3">Underwriter</th><th className="pr-3 text-right">Premium</th><th>Staff · branch</th></tr>
                  </thead>
                  <tbody>
                    {summary.expiring.map((e) => (
                      <tr key={e.id} className="border-t border-neutral-border">
                        <td className="py-1.5 pr-3 whitespace-nowrap">{dmy(e.expiry_date)}</td>
                        <td className="pr-3 font-medium">{e.client_name}</td>
                        <td className="pr-3">{e.phone ?? <span className="text-ink-soft">no phone in the sheet</span>}</td>
                        <td className="pr-3">{e.reg_no ?? e.asset_ref ?? "-"}</td>
                        <td className="pr-3">{e.underwriter ?? "-"}</td>
                        <td className="pr-3 text-right">{kes(e.premium)}</td>
                        <td>{[e.staff_name, e.branch].filter(Boolean).join(" · ") || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

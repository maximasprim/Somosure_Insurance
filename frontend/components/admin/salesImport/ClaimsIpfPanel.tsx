"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import { BASE, dmy, type EntryOptions, EVENT_LABELS, type IpfRow, kes, type LegacyClaim, OUTCOME_LABELS } from "@/lib/salesImport";

export function ClaimsIpfPanel({ refreshKey }: { refreshKey: number }) {
  const [years, setYears] = useState<number[]>([]);
  const [year, setYear] = useState("");
  const [q, setQ] = useState("");
  const [claims, setClaims] = useState<LegacyClaim[]>([]);
  const [ipf, setIpf] = useState<IpfRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [optionsLoaded, setOptionsLoaded] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);

  useEffect(() => {
    api
      .get<EntryOptions>(`${BASE}/entries/options`)
      .then((o) => setYears(o.years))
      .catch(() => undefined)
      .finally(() => setOptionsLoaded(true));
  }, [refreshKey]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (year) params.set("year", year);
    const claimParams = new URLSearchParams(params);
    if (q) claimParams.set("q", q);
    setError(null);
    Promise.all([api.get<LegacyClaim[]>(`${BASE}/claims?${claimParams}`), api.get<IpfRow[]>(`${BASE}/ipf?${params}`)])
      .then(([c, i]) => {
        setClaims(c);
        setIpf(i);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load"))
      .finally(() => setDataLoaded(true));
  }, [year, q, refreshKey]);

  if (!optionsLoaded || !dataLoaded) return <TabSkeleton />;

  const tone = (o: string) => (o === "closed" ? "success" : o === "action_needed" ? "error" : "neutral");

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium">Year</label>
          <select className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={year} onChange={(e) => setYear(e.target.value)}>
            <option value="">All</option>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <div className="flex-1">
          <Input label="Search claims by client, plate or text" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {error && <p className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <h2 className="text-lg font-semibold">Claims ({claims.length})</h2>
      {claims.length === 0 && <p className="text-ink-soft">No claims in the ledger.</p>}
      {claims.map((c) => (
        <Card key={c.id} className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="font-semibold">{c.client_name}</span>{" "}
              <span className="text-xs text-ink-soft">
                {c.reg_or_policy ?? ""} · {c.underwriter ?? "-"} · reported {dmy(c.date_reported)}
                {c.contact ? ` · ${c.contact}` : ""}
              </span>
            </div>
            <span className="flex gap-2">
              {c.status === "missing_from_sheet" && <Badge tone="error">Not in sheet</Badge>}
              <Badge tone={tone(c.outcome)}>{OUTCOME_LABELS[c.outcome] ?? c.outcome}</Badge>
            </span>
          </div>
          {c.milestones && c.milestones.length > 0 && (
            <ol className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs">
              {c.milestones.map((m, i) => (
                <li key={i}>
                  <span className="font-medium">{EVENT_LABELS[m.event] ?? m.event}</span> <span className="text-ink-soft">{dmy(m.date)}</span>
                </li>
              ))}
            </ol>
          )}
          {c.narrative && (
            <details className="mt-2 text-xs text-ink-soft">
              <summary className="cursor-pointer">Notes as written in the sheet</summary>
              <p className="mt-1 whitespace-pre-wrap">{c.narrative}</p>
            </details>
          )}
        </Card>
      ))}

      <h2 className="mt-2 text-lg font-semibold">IPF remittances ({ipf.length})</h2>
      <Card className="p-4">
        {ipf.length === 0 ? (
          <p className="text-ink-soft">No IPF lines in the ledger.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-ink-soft">
                <tr><th className="py-1 pr-3">Date paid</th><th className="pr-3">Insurer</th><th className="pr-3">Details</th><th className="text-right">Amount (KES)</th></tr>
              </thead>
              <tbody>
                {ipf.map((r) => (
                  <tr key={r.id} className="border-t border-neutral-border">
                    <td className="py-1.5 pr-3 whitespace-nowrap">{dmy(r.date_paid)}</td>
                    <td className="pr-3">{r.underwriter ?? "-"}</td>
                    <td className="pr-3">{r.details ?? "-"}</td>
                    <td className="text-right">{kes(r.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

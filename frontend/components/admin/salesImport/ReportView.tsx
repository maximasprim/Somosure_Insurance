"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import {
  type Counts,
  type ImportReport,
  ISSUE_LABELS,
  kes,
  monthLabel,
  periodLabel,
} from "@/lib/salesImport";

function CountsCard({ title, counts }: { title: string; counts: Counts }) {
  const cells: [string, number, string][] = [
    ["New", counts.new, "text-status-success"],
    ["Changed", counts.updated, "text-ink"],
    ["Unchanged", counts.unchanged, "text-ink-soft"],
    ["Not in sheet", counts.missing, counts.missing ? "text-status-error" : "text-ink-soft"],
  ];
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="text-xs text-ink-soft">{counts.total} rows in the file</p>
      <div className="mt-3 grid grid-cols-4 gap-2 text-center">
        {cells.map(([label, value, tone]) => (
          <div key={label}>
            <div className={`text-xl font-bold ${tone}`}>{value}</div>
            <div className="text-[11px] text-ink-soft">{label}</div>
          </div>
        ))}
      </div>
      {counts.restored > 0 && <p className="mt-2 text-xs text-ink-soft">{counts.restored} returned to the sheet and are active again.</p>}
    </Card>
  );
}

/** What the file contains and what importing it would do. Shown for both the check and the finished import. */
export function ReportView({ report }: { report: ImportReport }) {
  const [showAllRecon, setShowAllRecon] = useState(false);
  const [showAllIssues, setShowAllIssues] = useState(false);

  const issueRows = Object.entries(report.issue_counts)
    .map(([code, v]) => ({ code, ...v }))
    .sort((a, b) => ({ error: 0, warning: 1, info: 2 }[a.severity] - { error: 0, warning: 1, info: 2 }[b.severity]) || b.count - a.count);
  const recon = showAllRecon ? report.reconciliation : report.reconciliation.filter((r) => r.status !== "ok");
  const issues = showAllIssues ? report.issues : report.issues.slice(0, 40);
  const tone = (s: string) => (s === "error" ? "error" : s === "warning" ? "brand" : "neutral");

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="grid gap-3 md:grid-cols-3">
        <CountsCard title="Sales" counts={report.counts.sales} />
        <CountsCard title="Claims" counts={report.counts.claims} />
        <CountsCard title="IPF remittances" counts={report.counts.ipf} />
      </div>

      <Card className="p-4 text-sm">
        {(report.period.from || report.period.to) && (
          <p className="mb-2 rounded-control bg-brand-tint px-3 py-2">
            Period: <strong>{report.period.from ? periodLabel(report.period.from) : "the beginning"}</strong> to{" "}
            <strong>{report.period.to ? periodLabel(report.period.to) : "the latest month"}</strong>.{" "}
            {report.period.skipped.sales + report.period.skipped.claims + report.period.skipped.ipf} rows outside this period were skipped
            ({report.period.skipped.sales} sales, {report.period.skipped.claims} claims, {report.period.skipped.ipf} IPF) and are left exactly as they are in the system.
          </p>
        )}
        <div className="flex flex-wrap gap-x-8 gap-y-1">
          <span>
            Sheets read: <strong>{report.sheets.map((s) => s.name).join(", ")}</strong>
          </span>
          <span>
            Premium in the file: <strong>KES {kes(report.totals.premium)}</strong>
          </span>
          <span>
            Commission: <strong>KES {kes(report.totals.commission)}</strong>
          </span>
        </div>
        {report.ignored_sheets.length > 0 && (
          <p className="mt-1 text-xs text-ink-soft">Not read (not a sales, claims or IPF sheet): {report.ignored_sheets.join(", ")}</p>
        )}
        {report.notes.map((n) => (
          <p key={n} className="mt-1 text-xs text-ink-soft">
            {n}
          </p>
        ))}
        {Object.entries(report.unknown_columns).map(([sheet, cols]) => (
          <p key={sheet} className="mt-1 text-xs text-ink-soft">
            {sheet}: extra columns kept but not used - {Array.from(new Set(cols)).join(", ")}
          </p>
        ))}
      </Card>

      {issueRows.length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-semibold">What to look at in the sheet</h3>
          <p className="text-xs text-ink-soft">Nothing is blocked - every row is imported. These are the things worth fixing in the sheet itself.</p>
          <ul className="mt-3 grid gap-x-6 gap-y-1.5 text-sm md:grid-cols-2">
            {issueRows.map((r) => (
              <li key={r.code} className="flex items-center justify-between gap-3">
                <span>{ISSUE_LABELS[r.code] ?? r.code}</span>
                <Badge tone={tone(r.severity)}>{r.count}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {report.reconciliation.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold">Month totals: the sheet&apos;s TOTAL rows against the rows above them</h3>
              <p className="text-xs text-ink-soft">The system always uses the rows. A mismatch means the sheet&apos;s own SUM does not cover every row.</p>
            </div>
            <button className="text-xs text-ink-soft underline" onClick={() => setShowAllRecon((v) => !v)}>
              {showAllRecon ? "Show only problems" : "Show every month"}
            </button>
          </div>
          {recon.length === 0 ? (
            <p className="mt-3 text-sm text-status-success">Every month&apos;s total agrees with its rows.</p>
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-ink-soft">
                  <tr>
                    <th className="py-1 pr-3">Month</th>
                    <th className="pr-3">Rows</th>
                    <th className="pr-3 text-right">Premium (rows)</th>
                    <th className="pr-3 text-right">Premium (sheet total)</th>
                    <th className="pr-3 text-right">Commission (rows)</th>
                    <th className="pr-3 text-right">Commission (sheet total)</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {recon.map((r, i) => (
                    <tr key={`${r.sheet}-${r.year}-${r.month}-${i}`} className="border-t border-neutral-border">
                      <td className="py-1.5 pr-3">
                        {monthLabel(r.month)} {r.year}
                      </td>
                      <td className="pr-3">{r.rows}</td>
                      <td className="pr-3 text-right">{kes(r.premium)}</td>
                      <td className={`pr-3 text-right ${r.difference.premium ? "font-semibold text-status-error" : ""}`}>{kes(r.sheet_premium)}</td>
                      <td className="pr-3 text-right">{kes(r.commission)}</td>
                      <td className={`pr-3 text-right ${r.difference.commission ? "font-semibold text-status-error" : ""}`}>{kes(r.sheet_commission)}</td>
                      <td>
                        {r.status === "ok" && <Badge tone="success">Agrees</Badge>}
                        {r.status === "mismatch" && <Badge tone="error">Total is wrong</Badge>}
                        {r.status === "no_total" && <Badge tone="neutral">No total row yet</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {report.changes_total > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-semibold">Rows that changed since the last import ({report.changes_total})</h3>
          <ul className="mt-3 flex flex-col gap-2 text-sm">
            {report.changes.map((c, i) => (
              <li key={i} className="rounded-control bg-neutral/60 px-3 py-2">
                <div className="font-medium">
                  {c.client_name ?? "-"} <span className="text-xs font-normal text-ink-soft">{c.policy_number ?? ""} · {c.sheet} row {c.row ?? "?"}</span>
                </div>
                <div className="mt-0.5 text-xs text-ink-soft">
                  {c.fields.map((f) => `${f.field}: ${f.old ?? "empty"} → ${f.new ?? "empty"}`).join("  ·  ")}
                </div>
              </li>
            ))}
          </ul>
          {report.changes_total > report.changes.length && <p className="mt-2 text-xs text-ink-soft">Showing the first {report.changes.length}.</p>}
        </Card>
      )}

      {report.missing_total > 0 && (
        <Card className="border-status-error/40 p-4">
          <h3 className="text-sm font-semibold">In the system but no longer in the sheet ({report.missing_total})</h3>
          <p className="text-xs text-ink-soft">These are kept and marked &quot;not in sheet&quot; - never deleted. They are active again if the row returns.</p>
          <ul className="mt-2 text-sm">
            {report.missing.map((m, i) => (
              <li key={i}>
                {m.client_name ?? "-"} <span className="text-xs text-ink-soft">{m.policy_number ?? ""} · {m.sheet} row {m.row ?? "?"}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {(report.new_aliases.underwriters.length > 0 || report.new_aliases.staff.length > 0) && (
        <Card className="p-4">
          <h3 className="text-sm font-semibold">Names the importer matched on its own</h3>
          <p className="text-xs text-ink-soft">Check them once on the Names tab; after that the same decision is used every week.</p>
          <ul className="mt-2 grid gap-x-6 text-sm md:grid-cols-2">
            {report.new_aliases.underwriters.map((u) => (
              <li key={`u-${u.typed}`}>
                {u.typed} → <strong>{u.canonical}</strong>
              </li>
            ))}
            {report.new_aliases.staff.slice(0, 30).map((s) => (
              <li key={`s-${s.typed}`}>
                {s.typed} → <strong>{[s.name, s.branch].filter(Boolean).join(" · ") || "-"}</strong>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {report.issues.length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-semibold">Rows to fix in the sheet ({report.issues_total})</h3>
          <ul className="mt-3 flex flex-col gap-1.5 text-sm">
            {issues.map((i, idx) => (
              <li key={idx} className="flex gap-2">
                <Badge tone={tone(i.severity)}>{i.severity}</Badge>
                <span>
                  <strong>{i.client_name ?? "-"}</strong> <span className="text-xs text-ink-soft">{i.sheet} row {i.row}</span>
                  <br />
                  <span className="text-xs text-ink-soft">{i.message}</span>
                </span>
              </li>
            ))}
          </ul>
          {report.issues.length > 40 && (
            <button className="mt-2 text-xs text-ink-soft underline" onClick={() => setShowAllIssues((v) => !v)}>
              {showAllIssues ? "Show fewer" : `Show all ${report.issues.length}`}
            </button>
          )}
        </Card>
      )}
    </div>
  );
}

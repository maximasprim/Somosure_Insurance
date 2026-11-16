"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { dmy, EVENT_LABELS, kes, OUTCOME_LABELS, PRODUCT_LABELS } from "@/lib/salesImport";
import { type CustomerHistory, SALES_BASE } from "@/lib/salesSync";

/** A customer's policies and claims from the weekly report workbook, on the customer page. Shows nothing at all
 *  when there is nothing (or when the workbook tables are not there yet), so it never clutters a normal customer. */
export function WorkbookHistory({ customerId }: { customerId: string }) {
  const [history, setHistory] = useState<CustomerHistory | null>(null);

  useEffect(() => {
    api
      .get<CustomerHistory>(`${SALES_BASE}/customers/${customerId}/history`)
      .then(setHistory)
      .catch(() => setHistory(null));
  }, [customerId]);

  if (!history || (history.entries.length === 0 && history.claims.length === 0)) return null;

  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold">Policies and claims from the weekly report</h2>
      <p className="text-sm text-ink-soft">Recorded in the workbook rather than sold through the platform. They follow the sheet.</p>

      <div className="mt-3 flex flex-col gap-2">
        {history.entries.map((e) => (
          <Card key={e.id} className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-semibold">{e.underwriter ?? "-"}</h3>
                <span className="text-sm text-ink-soft">{e.reg_no ?? e.asset_ref ?? PRODUCT_LABELS[e.product_line] ?? ""}</span>
                {e.business_type && <Badge tone="neutral">{e.business_type === "new_business" ? "New business" : "Renewal"}</Badge>}
              </div>
              <p className="mt-1 text-xs text-ink-soft">
                {e.policy_number ?? "no policy number"} · {dmy(e.start_date)} to {dmy(e.expiry_date)} · {[e.staff_name, e.branch].filter(Boolean).join(" · ") || "no staff recorded"}
              </p>
            </div>
            <span className="text-sm font-medium">KES {kes(e.premium)}</span>
          </Card>
        ))}
        {history.claims.map((c) => (
          <Card key={c.id} className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold">Claim reported {dmy(c.date_reported)}</span>
              <Badge tone={c.outcome === "closed" ? "success" : c.outcome === "action_needed" ? "error" : "neutral"}>{OUTCOME_LABELS[c.outcome] ?? c.outcome}</Badge>
            </div>
            {c.milestones && c.milestones.length > 0 && (
              <ol className="flex flex-wrap gap-x-5 gap-y-1 text-xs">
                {c.milestones.map((m, i) => (
                  <li key={i}>
                    <span className="font-medium">{EVENT_LABELS[m.event] ?? m.event}</span> <span className="text-ink-soft">{dmy(m.date)}</span>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        ))}
      </div>
    </section>
  );
}

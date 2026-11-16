"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card } from "@/components/ui/Card";
import { COLORS, compactKes, formatCount, formatKes } from "@/lib/analytics";
import type { WorkbookAnalytics } from "@/lib/salesSync";
import { Donut, HBars, KpiTile, Panel } from "./AnalyticsCharts";

function monthLabel(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return d.toLocaleDateString("en-KE", { month: "short", year: "2-digit" });
}

/** "All sales": the platform's sales and the weekly report workbook's, together. Sits below the existing
 *  platform-only sections of the dashboard and changes none of them. */
export function AllSalesSection({ data }: { data: Partial<WorkbookAnalytics> | undefined }) {
  const hasData = !!data && !!data.kpis && ((data.monthly?.length ?? 0) > 0 || (data.kpis.sales?.value ?? 0) > 0);
  const title = <h2 className="mt-10 text-xs font-semibold uppercase tracking-wider text-ink-soft">All sales - platform and weekly report together</h2>;

  if (!data || !data.kpis || !hasData) {
    return (
      <>
        {title}
        <Card className="mt-3 text-sm text-ink-soft">
          No workbook sales in this period yet. Import the weekly report on the{" "}
          <a href="/admin/sales-import" className="text-brand-deep underline">Sales import</a> page and they appear here next to the platform&apos;s own sales.
        </Card>
      </>
    );
  }

  const k = data.kpis;
  const monthly = (data.monthly ?? []).map((m) => ({ name: monthLabel(m.date), Premium: m.premium, Commission: m.commission }));
  const covered = data.coverage?.workbook_from && data.coverage?.workbook_to ? `${data.coverage.workbook_from} to ${data.coverage.workbook_to}` : null;

  return (
    <>
      {title}
      <p className="mt-1 text-xs text-ink-soft">
        Each sale is counted once. Workbook sales are dated by the date paid{covered ? ` (workbook covers ${covered})` : ""}; demo policies are left out.
        Workbook rows that have been posted into the system are already inside the sections above; this section also counts rows not posted yet.
      </p>
      <div className="mt-3 grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiTile label="All sales" kpi={k.sales} format={formatCount} />
        <KpiTile label="Premium" kpi={k.premium} format={compactKes} />
        <KpiTile label="Commission" kpi={k.commission} format={compactKes} />
        <KpiTile label="Net revenue" kpi={k.net_revenue} format={compactKes} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel title="Premium and commission by month" subtitle="All sales in this period" className="lg:col-span-2">
          {monthly.length === 0 ? (
            <p className="flex h-40 items-center justify-center text-sm text-ink-soft">Nothing recorded in this period.</p>
          ) : (
            <div style={{ height: 260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthly} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke={COLORS.grid} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: COLORS.inkSoft }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: COLORS.inkSoft }} tickLine={false} axisLine={false} tickFormatter={(v: number) => compactKes(v).replace("KES ", "")} width={48} />
                  <Tooltip formatter={(value: number) => formatKes(Number(value))} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Premium" fill={COLORS.brand} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Commission" fill={COLORS.ink} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
        <Panel title="Where sales came from" subtitle="Premium, platform vs workbook">
          <Donut rows={data.sources ?? []} metric="amount" />
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel title="Premium by underwriter" subtitle="Share of premium, all sales">
          <Donut rows={data.by_underwriter ?? []} metric="amount" />
        </Panel>
        <Panel title="Sales by branch" subtitle="Number of policies">
          <HBars rows={data.by_branch ?? []} color={COLORS.brandDeep} />
        </Panel>
        <Panel title="Sales by staff" subtitle="Number of policies">
          <HBars rows={data.by_staff ?? []} color={COLORS.ink} />
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel title="New business and renewals" subtitle="Premium, where the sheet says which">
          <Donut rows={data.by_business_type ?? []} metric="amount" />
        </Panel>
        <Panel title="Product mix" subtitle="Premium by product">
          <Donut rows={data.by_product ?? []} metric="amount" />
        </Panel>
        <Panel title="Workbook claims" subtitle="Reported in this period">
          <HBars rows={data.claims ?? []} />
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Card className="flex flex-col gap-1 !p-4">
          <span className="text-xs font-medium uppercase tracking-wide text-ink-soft">Workbook renewals due (60 days)</span>
          <span className="font-display text-2xl font-extrabold">{formatCount(data.renewals?.due_60d ?? 0)}</span>
          <a href="/admin/sales?tab=renewals" className="text-xs text-brand-deep underline">Open the renewals list</a>
        </Card>
        <Card className="flex flex-col gap-1 !p-4">
          <span className="text-xs font-medium uppercase tracking-wide text-ink-soft">Workbook renewals overdue (30 days)</span>
          <span className="font-display text-2xl font-extrabold">{formatCount(data.renewals?.overdue_30d ?? 0)}</span>
          <a href="/admin/sales?tab=renewals" className="text-xs text-brand-deep underline">Follow them up</a>
        </Card>
        <Card className="flex flex-col gap-1 !p-4">
          <span className="text-xs font-medium uppercase tracking-wide text-ink-soft">Workbook clients matched to customers</span>
          <span className="font-display text-2xl font-extrabold">
            {formatCount(data.customers?.linked_to_customers ?? 0)} <span className="text-base font-medium text-ink-soft">of {formatCount(data.customers?.workbook_clients ?? 0)}</span>
          </span>
          <a href="/admin/sales?tab=customers" className="text-xs text-brand-deep underline">Match the rest</a>
        </Card>
      </div>
    </>
  );
}

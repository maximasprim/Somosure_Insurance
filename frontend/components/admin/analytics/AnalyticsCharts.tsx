"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/ui/Card";
import {
  COLORS,
  bucketLabel,
  colorFor,
  compactKes,
  describeChange,
  formatCount,
  formatKes,
  funnelRates,
  titleCase,
  total,
  type Analytics,
  type FunnelStep,
  type KpiValue,
  type NamedCount,
  type ProviderRow,
  type TrendPoint,
} from "@/lib/analytics";

const AXIS = { fontSize: 11, fill: COLORS.inkSoft };

// --- building blocks ---------------------------------------------------------

export function Panel({
  title,
  subtitle,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={`flex flex-col ${className ?? ""}`}>
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {subtitle && <p className="mt-0.5 text-xs text-ink-soft">{subtitle}</p>}
      <div className="mt-4 flex-1">{children}</div>
    </Card>
  );
}

function Empty({ text = "Nothing recorded in this period." }: { text?: string }) {
  return <p className="flex h-40 items-center justify-center text-center text-sm text-ink-soft">{text}</p>;
}

interface TipItem {
  name?: string;
  value?: number | string;
  color?: string;
  payload?: Record<string, unknown>;
}

/** One tooltip for every chart: a small white card with a colour dot per line. */
function ChartTooltip({
  active,
  payload,
  label,
  money,
  labelFormat,
}: {
  active?: boolean;
  payload?: TipItem[];
  label?: string | number;
  /** series names (or a data key) whose values are KES amounts */
  money?: string[];
  labelFormat?: (label: string) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  // Pie slices have no axis label; their name is already on the row below.
  const heading = label !== undefined ? (labelFormat ? labelFormat(String(label)) : String(label)) : undefined;
  return (
    <div className="rounded-control border border-neutral-border bg-white px-3 py-2 text-xs shadow-card">
      {heading !== undefined && <p className="mb-1 font-semibold text-ink">{heading}</p>}
      {payload.map((item) => {
        const isMoney = money?.includes(String(item.name));
        const value = Number(item.value ?? 0);
        const extra = item.payload && typeof item.payload.amount === "number" ? (item.payload.amount as number) : null;
        return (
          <p key={String(item.name)} className="flex items-center gap-2 text-ink-soft">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: item.color ?? COLORS.ink }} />
            <span>{item.name}</span>
            <span className="ml-auto pl-3 font-medium text-ink">{isMoney ? formatKes(value) : formatCount(value)}</span>
            {extra !== null && <span className="text-ink-soft">· {formatKes(extra)}</span>}
          </p>
        );
      })}
    </div>
  );
}

// --- headline tiles ------------------------------------------------------------

const DELTA_TONE: Record<string, string> = {
  up: "bg-status-success/10 text-status-success",
  down: "bg-status-error/10 text-status-error",
  flat: "bg-neutral text-ink-soft",
  new: "bg-brand-tint text-ink",
};

export function KpiTile({
  label,
  kpi,
  format,
  rate,
}: {
  label: string;
  kpi: KpiValue | undefined;
  format: (n: number) => string;
  rate?: boolean;
}) {
  const delta = describeChange(kpi, rate);
  return (
    <Card className="flex flex-col gap-1.5 !p-4">
      <span className="text-xs font-medium uppercase tracking-wide text-ink-soft">{label}</span>
      <span className="font-display text-2xl font-extrabold text-ink">{kpi ? format(kpi.value) : "-"}</span>
      <span className={`inline-flex w-fit items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${DELTA_TONE[delta.tone]}`}>
        {delta.text}
      </span>
    </Card>
  );
}

// --- needs attention --------------------------------------------------------------

export function AttentionStrip({ snapshot }: { snapshot: Analytics["snapshot"] }) {
  const items: { label: string; value: number | undefined; href: string }[] = [
    { label: "Applications awaiting review", value: snapshot.applications_awaiting_review, href: "/admin/applications" },
    { label: "Open claims", value: snapshot.open_claims, href: "/admin/claims" },
    { label: "Renewals due", value: snapshot.renewals_due, href: "/admin/renewals" },
    { label: "Policies expiring in 30 days", value: snapshot.expiring_30d, href: "/admin/policies" },
    { label: "Payments pending", value: snapshot.pending_payments, href: "/admin/payments" },
    { label: "Financing awaiting decision", value: snapshot.financing_awaiting_decision, href: "/admin/financing" },
    { label: "Overdue instalments", value: snapshot.overdue_installments, href: "/admin/financing" },
    { label: "Stickers in progress", value: snapshot.stickers_in_progress, href: "/admin/stickers" },
  ];
  if (items.every((i) => i.value === undefined)) return null;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {items.map((item) => {
        const hot = (item.value ?? 0) > 0;
        return (
          <Link
            key={item.label}
            href={item.href}
            className={`rounded-control border px-4 py-3 transition-colors hover:border-brand-deep ${
              hot ? "border-brand/60 bg-brand-tint/60" : "border-neutral-border bg-white"
            }`}
          >
            <span className="block font-display text-xl font-extrabold text-ink">{item.value === undefined ? "-" : formatCount(item.value)}</span>
            <span className="block text-xs text-ink-soft">{item.label}</span>
          </Link>
        );
      })}
    </div>
  );
}

// --- trends -------------------------------------------------------------------------

export function RevenueTrend({ data, bucket }: { data: TrendPoint[]; bucket: Analytics["bucket"] }) {
  if (data.length === 0 || data.every((p) => p.revenue === 0 && p.policies === 0)) {
    return <Empty text="No payments or policies in this period yet." />;
  }
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLORS.brand} stopOpacity={0.55} />
              <stop offset="100%" stopColor={COLORS.brand} stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke={COLORS.grid} />
          <XAxis dataKey="date" tick={AXIS} tickLine={false} axisLine={false} minTickGap={24} tickFormatter={(v) => bucketLabel(String(v), bucket)} />
          <YAxis yAxisId="money" tick={AXIS} tickLine={false} axisLine={false} width={64} tickFormatter={(v) => compactKes(Number(v))} />
          <YAxis yAxisId="count" orientation="right" tick={AXIS} tickLine={false} axisLine={false} width={32} allowDecimals={false} />
          <Tooltip
            content={<ChartTooltip money={["Revenue collected", "Premium written"]} labelFormat={(l) => bucketLabel(l, bucket)} />}
          />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Area yAxisId="money" type="monotone" dataKey="revenue" name="Revenue collected" stroke={COLORS.brandDeep} strokeWidth={2} fill="url(#revenueFill)" />
          <Bar yAxisId="count" dataKey="policies" name="Policies issued" fill={COLORS.ink} barSize={10} radius={[3, 3, 0, 0]} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ActivityTrend({ data, bucket }: { data: TrendPoint[]; bucket: Analytics["bucket"] }) {
  if (data.length === 0 || data.every((p) => p.quote_requests + p.applications + p.customers + p.claims === 0)) {
    return <Empty text="No customer activity in this period yet." />;
  }
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={COLORS.grid} />
          <XAxis dataKey="date" tick={AXIS} tickLine={false} axisLine={false} minTickGap={24} tickFormatter={(v) => bucketLabel(String(v), bucket)} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={32} allowDecimals={false} />
          <Tooltip content={<ChartTooltip labelFormat={(l) => bucketLabel(l, bucket)} />} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="quote_requests" name="Quote requests" stroke={COLORS.brandDeep} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="applications" name="Applications" stroke={COLORS.ink} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="customers" name="New customers" stroke={COLORS.info} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="claims" name="Claims" stroke={COLORS.error} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// --- funnel (plain bars - no chart library needed) --------------------------------------

export function Funnel({ steps }: { steps: FunnelStep[] }) {
  const rows = funnelRates(steps);
  if (rows.length === 0 || rows[0].value === 0) return <Empty text="No quote requests in this period yet." />;
  return (
    <ol className="flex flex-col gap-3">
      {rows.map((row, i) => (
        <li key={row.name}>
          <div className="flex items-baseline justify-between text-xs">
            <span className="font-medium text-ink">{row.name}</span>
            <span className="text-ink-soft">
              <span className="font-semibold text-ink">{formatCount(row.value)}</span>
              {row.ofPrevious !== null && ` · ${Math.round(row.ofPrevious)}% of previous`}
            </span>
          </div>
          <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-neutral">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.max(row.ofFirst, row.value > 0 ? 2 : 0)}%`,
                background: i === rows.length - 1 ? COLORS.success : COLORS.brand,
              }}
            />
          </div>
        </li>
      ))}
    </ol>
  );
}

// --- breakdown charts ------------------------------------------------------------------------

/** A donut with its legend alongside: name, value and share. `metric` picks counts or KES amounts. */
export function Donut({ rows, metric = "count" }: { rows: NamedCount[]; metric?: "count" | "amount" }) {
  const data = rows
    .map((r) => ({ name: titleCase(r.name), value: metric === "amount" ? r.amount ?? 0 : r.count, raw: r.name }))
    .filter((r) => r.value > 0);
  const sum = data.reduce((s, r) => s + r.value, 0);
  if (data.length === 0) return <Empty />;
  const show = (n: number) => (metric === "amount" ? compactKes(n) : formatCount(n));
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row">
      <div className="relative h-40 w-40 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={48} outerRadius={72} paddingAngle={data.length > 1 ? 2 : 0} stroke="none">
              {data.map((row, i) => (
                <Cell key={row.raw} fill={colorFor(row.raw, i)} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip money={metric === "amount" ? data.map((d) => d.name) : []} />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-lg font-extrabold text-ink">{show(sum)}</span>
          <span className="text-[10px] uppercase tracking-wide text-ink-soft">total</span>
        </div>
      </div>
      <ul className="w-full min-w-0 flex-1 text-xs">
        {data.map((row, i) => (
          <li key={row.raw} className="flex items-center gap-2 border-b border-neutral-border/60 py-1.5 last:border-0">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: colorFor(row.raw, i) }} />
            <span className="min-w-0 flex-1 truncate text-ink-soft">{row.name}</span>
            <span className="font-medium text-ink">{show(row.value)}</span>
            <span className="w-9 text-right text-ink-soft">{Math.round((row.value / sum) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Horizontal bars, one per status/category, coloured by meaning. */
export function HBars({ rows, color }: { rows: NamedCount[]; color?: string }) {
  const data = rows.map((r) => ({ name: titleCase(r.name), count: r.count, amount: r.amount, raw: r.name }));
  if (data.length === 0 || total(rows) === 0) return <Empty />;
  return (
    <div style={{ height: Math.max(170, data.length * 34 + 24) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid horizontal={false} stroke={COLORS.grid} />
          <XAxis type="number" tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
          <YAxis type="category" dataKey="name" width={120} tick={AXIS} tickLine={false} axisLine={false} />
          <Tooltip cursor={{ fill: "#F4F5F7" }} content={<ChartTooltip />} />
          <Bar dataKey="count" name="Count" radius={[0, 4, 4, 0]} barSize={16}>
            {data.map((row, i) => (
              <Cell key={row.raw} fill={color ?? colorFor(row.raw, i)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ProviderBars({ rows }: { rows: ProviderRow[] }) {
  if (rows.length === 0) return <Empty text="No provider activity in this period yet." />;
  const data = rows.map((r) => ({ ...r, label: r.name.length > 16 ? `${r.name.slice(0, 15)}…` : r.name }));
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={COLORS.grid} />
          <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} interval={0} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={32} allowDecimals={false} />
          <Tooltip cursor={{ fill: "#F4F5F7" }} content={<ChartTooltip />} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="quotes" name="Quotes returned" fill={COLORS.brand} radius={[4, 4, 0, 0]} />
          <Bar dataKey="policies" name="Policies issued" fill={COLORS.ink} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

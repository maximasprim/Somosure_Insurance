// Types, colours and number formatting for the admin Reports & analytics
// dashboard (app/admin/page.tsx). The data comes from
// GET /api/v1/admin/reports/analytics. Pure functions, no React.

export const RANGE_OPTIONS = [
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
  { days: 365, label: "12 months" },
] as const;

export interface KpiValue {
  value: number;
  previous: number;
  /** Percentage change vs the previous period; null when there was nothing to compare with. */
  change_pct: number | null;
  /** Only for rates (conversion): change in percentage points. */
  change_pts?: number;
}

export interface NamedCount {
  name: string;
  count: number;
  amount?: number;
}

export interface TrendPoint {
  date: string; // ISO date of the bucket start
  revenue: number;
  premium: number;
  policies: number;
  quote_requests: number;
  applications: number;
  customers: number;
  claims: number;
}

export interface FunnelStep {
  name: string;
  value: number;
}

export interface ProviderRow {
  name: string;
  quotes: number;
  policies: number;
  premium: number;
}

export interface AnalyticsSnapshot {
  active_policies: number;
  demo_policies_in_period: number;
  expiring_30d: number;
  renewals_due: number;
  applications_awaiting_review: number;
  open_claims: number;
  financing_awaiting_decision: number;
  overdue_installments: number;
  pending_payments: number;
  stickers_in_progress: number;
}

export interface Analytics {
  range_days: number;
  bucket: "day" | "week" | "month";
  generated_at: string;
  period: { start: string; end: string };
  kpis: Record<string, KpiValue>;
  snapshot: Partial<AnalyticsSnapshot>;
  trend: TrendPoint[];
  funnel: FunnelStep[];
  quotes_by_category: NamedCount[];
  premium_by_category: NamedCount[];
  providers: ProviderRow[];
  policies_by_source: NamedCount[];
  payments_by_status: NamedCount[];
  payments_by_method: NamedCount[];
  applications_by_status: NamedCount[];
  claims_by_status: NamedCount[];
  leads_by_stage: NamedCount[];
  leads_by_source: NamedCount[];
  financing_by_status: NamedCount[];
  agreements_by_status: NamedCount[];
  renewals_by_status: NamedCount[];
  stickers_by_status: NamedCount[];
  commissions_by_status: NamedCount[];
  referrals_by_status: NamedCount[];
  /** Sections the server could not compute (the rest of the page still works). */
  unavailable: string[];
}

// --- colours (the site's own palette) ---------------------------------------

export const COLORS = {
  brand: "#FFC53D",
  brandDeep: "#E8A100",
  ink: "#1A1D21",
  inkSoft: "#565B64",
  grid: "#EEF0F2",
  success: "#1F9254",
  error: "#C5432B",
  info: "#2563EB",
  muted: "#B9BDC4",
};

export const PALETTE = [COLORS.brand, COLORS.ink, COLORS.info, COLORS.success, COLORS.brandDeep, COLORS.error, "#8A8F98", COLORS.muted];

const GOOD = new Set(["approved", "active", "paid", "successful", "won", "renewed", "settled", "delivered", "completed", "converted", "rewarded", "generated"]);
const BAD = new Set(["rejected", "failed", "lost", "overdue", "cancelled", "defaulted", "expired", "reversed", "unknown"]);
const WAITING = new Set(["pending", "initiated", "due", "new", "submitted", "draft", "documents_required", "reported", "eligibility_checked"]);

/** Statuses read at a glance: green = done well, red = lost/failed, amber = waiting. Anything else cycles the palette. */
export function colorFor(name: string, index: number): string {
  const key = name.toLowerCase();
  if (GOOD.has(key)) return COLORS.success;
  if (BAD.has(key)) return COLORS.error;
  if (WAITING.has(key)) return COLORS.brand;
  return PALETTE[(index + 1) % PALETTE.length];
}

// --- formatting ---------------------------------------------------------------

export function titleCase(text: string): string {
  return text.replace(/_/g, " ").replace(/\s+/g, " ").trim().replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatKes(amount: number): string {
  return `KES ${Math.round(amount).toLocaleString("en-KE")}`;
}

/** KES 1.2M / KES 45K / KES 800 - for tiles and axis ticks. */
export function compactKes(amount: number): string {
  const abs = Math.abs(amount);
  const trim = (n: number) => n.toFixed(1).replace(/\.0$/, "");
  if (abs >= 1_000_000_000) return `KES ${trim(amount / 1_000_000_000)}B`;
  if (abs >= 1_000_000) return `KES ${trim(amount / 1_000_000)}M`;
  if (abs >= 1_000) return `KES ${trim(amount / 1_000)}K`;
  return `KES ${Math.round(amount)}`;
}

export function formatCount(n: number): string {
  return Math.round(n).toLocaleString("en-KE");
}

/** "14 Oct" for days and weeks, "Oct 26" for months. */
export function bucketLabel(iso: string, bucket: "day" | "week" | "month"): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  if (bucket === "month") return d.toLocaleDateString("en-KE", { month: "short", year: "2-digit" });
  return d.toLocaleDateString("en-KE", { day: "numeric", month: "short" });
}

export interface Delta {
  text: string;
  tone: "up" | "down" | "flat" | "new";
}

/** How a headline figure moved against the previous period. */
export function describeChange(kpi: KpiValue | undefined, rate = false): Delta {
  if (!kpi) return { text: "-", tone: "flat" };
  if (rate && kpi.change_pts !== undefined) {
    if (kpi.change_pts === 0) return { text: "no change", tone: "flat" };
    const arrow = kpi.change_pts > 0 ? "▲" : "▼";
    return { text: `${arrow} ${Math.abs(kpi.change_pts)} pts`, tone: kpi.change_pts > 0 ? "up" : "down" };
  }
  if (kpi.change_pct === null) {
    return kpi.value > 0 ? { text: "new this period", tone: "new" } : { text: "no activity", tone: "flat" };
  }
  if (kpi.change_pct === 0) return { text: "no change", tone: "flat" };
  const arrow = kpi.change_pct > 0 ? "▲" : "▼";
  return { text: `${arrow} ${Math.abs(kpi.change_pct)}%`, tone: kpi.change_pct > 0 ? "up" : "down" };
}

/** Each step of the funnel as a share of the first, and of the step before it. */
export function funnelRates(steps: FunnelStep[]): { name: string; value: number; ofFirst: number; ofPrevious: number | null }[] {
  const first = steps[0]?.value ?? 0;
  return steps.map((step, i) => ({
    name: step.name,
    value: step.value,
    ofFirst: first > 0 ? (step.value / first) * 100 : 0,
    ofPrevious: i === 0 ? null : steps[i - 1].value > 0 ? (step.value / steps[i - 1].value) * 100 : null,
  }));
}

export function total(rows: { count: number }[]): number {
  return rows.reduce((sum, r) => sum + r.count, 0);
}

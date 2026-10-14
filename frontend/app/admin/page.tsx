"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { AdminQuickLinks } from "@/components/admin/AdminQuickLinks";
import {
  ActivityTrend,
  AttentionStrip,
  Donut,
  Funnel,
  HBars,
  KpiTile,
  Panel,
  ProviderBars,
  RevenueTrend,
} from "@/components/admin/analytics/AnalyticsCharts";
import { api, downloadFile } from "@/lib/api";
import { COLORS, RANGE_OPTIONS, compactKes, formatCount, titleCase, type Analytics } from "@/lib/analytics";

function RangePicker({ days, onChange, disabled }: { days: number; onChange: (d: number) => void; disabled: boolean }) {
  return (
    <div className="inline-flex rounded-control border border-neutral-border bg-white p-0.5" role="group" aria-label="Reporting period">
      {RANGE_OPTIONS.map((option: (typeof RANGE_OPTIONS)[number]) => (
        <button
          key={option.days}
          type="button"
          disabled={disabled}
          onClick={() => onChange(option.days)}
          className={`rounded-[8px] px-3 py-1.5 text-xs font-semibold transition-colors ${
            days === option.days ? "bg-ink text-white" : "text-ink-soft hover:bg-neutral"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="mt-10 text-xs font-semibold uppercase tracking-wider text-ink-soft">{children}</h2>;
}

function Skeleton() {
  return (
    <div className="mt-6 animate-pulse">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-24 rounded-card bg-neutral" />
        ))}
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="h-80 rounded-card bg-neutral lg:col-span-2" />
        <div className="h-80 rounded-card bg-neutral" />
      </div>
    </div>
  );
}

export default function AdminAnalyticsPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const load = useCallback(async (range: number) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<Analytics>(`/api/v1/admin/reports/analytics?days=${range}`);
      setData(result);
      setForbidden(false);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Could not load the analytics";
      // Staff roles without report access (e.g. underwriters) still land here;
      // they get the shortcuts instead of an error.
      if (/insufficient permissions|403/i.test(message)) setForbidden(true);
      else setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(days);
  }, [days, load]);

  async function exportProviders() {
    setExportError(null);
    try {
      await downloadFile("/api/v1/admin/reports/provider-performance/export.csv", "provider_performance.csv");
    } catch (e) {
      setExportError(e instanceof Error ? e.message : "Could not export");
    }
  }

  const k = data?.kpis ?? {};
  const rangeLabel = RANGE_OPTIONS.find((o) => o.days === days)?.label ?? `${days} days`;

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Reports &amp; analytics</h1>
          <p className="mt-1 text-sm text-ink-soft">
            {forbidden
              ? "Shortcuts to everything staff can manage."
              : `How the business is doing over the last ${rangeLabel.toLowerCase()}, compared with the period before.`}
          </p>
        </div>
        {!forbidden && (
          <div className="flex flex-wrap items-center gap-2">
            <RangePicker days={days} onChange={setDays} disabled={loading} />
            <Button variant="ghost" onClick={() => load(days)} disabled={loading} aria-label="Refresh">
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
            <Button variant="ghost" onClick={exportProviders}>
              <Download className="mr-1.5 h-4 w-4" /> Providers CSV
            </Button>
          </div>
        )}
      </div>

      {exportError && <p className="mt-2 text-sm text-status-error">{exportError}</p>}

      {forbidden && (
        <Card className="mt-6 text-sm text-ink-soft">
          The analytics are available to management, finance and admin roles. Your role can still use everything below.
        </Card>
      )}

      {error && (
        <Card className="mt-6 flex items-center justify-between gap-3 text-sm">
          <span className="text-status-error">{error}</span>
          <Button variant="ghost" onClick={() => load(days)}>
            Try again
          </Button>
        </Card>
      )}

      {loading && !data && !forbidden && <Skeleton />}

      {data && !forbidden && (
        <div className={loading ? "opacity-60 transition-opacity" : "transition-opacity"}>
          {data.unavailable.length > 0 && (
            <p className="mt-4 rounded-control bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Some figures couldn&apos;t be loaded just now: {data.unavailable.map((n) => titleCase(n)).join(", ")}. The rest is up to date.
            </p>
          )}

          {/* Headline figures */}
          <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
            <KpiTile label="Revenue collected" kpi={k.revenue} format={compactKes} />
            <KpiTile label="Premium written" kpi={k.premium_written} format={compactKes} />
            <KpiTile label="Policies issued" kpi={k.policies_issued} format={formatCount} />
            <KpiTile label="Commission" kpi={k.commission} format={compactKes} />
            <KpiTile label="Quote requests" kpi={k.quote_requests} format={formatCount} />
            <KpiTile label="Applications" kpi={k.applications} format={formatCount} />
            <KpiTile label="Quote → policy" kpi={k.conversion_pct} format={(n: number) => `${n}%`} rate />
            <KpiTile label="New customers" kpi={k.new_customers} format={formatCount} />
          </div>
          {(data.snapshot.demo_policies_in_period ?? 0) > 0 && (
            <p className="mt-2 text-xs text-ink-soft">
              Includes {formatCount(data.snapshot.demo_policies_in_period ?? 0)} demo (test) polic
              {data.snapshot.demo_policies_in_period === 1 ? "y" : "ies"} from the mock insurers.
            </p>
          )}

          <SectionTitle>Needs attention now</SectionTitle>
          <div className="mt-3">
            <AttentionStrip snapshot={data.snapshot} />
          </div>

          <SectionTitle>Sales &amp; revenue</SectionTitle>
          <div className="mt-3 grid gap-4 lg:grid-cols-3">
            <Panel title="Revenue and policies" subtitle="Payments collected (area) and policies issued (bars)" className="lg:col-span-2">
              <RevenueTrend data={data.trend} bucket={data.bucket} />
            </Panel>
            <Panel title="Sales funnel" subtitle="From quote request to issued policy">
              <Funnel steps={data.funnel} />
            </Panel>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <Panel title="Customer activity" subtitle="Quotes, applications, new customers and claims" className="lg:col-span-2">
              <ActivityTrend data={data.trend} bucket={data.bucket} />
            </Panel>
            <Panel title="Premium by product" subtitle="Share of premium written">
              <Donut rows={data.premium_by_category} metric="amount" />
            </Panel>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <Panel title="Provider performance" subtitle="Quotes returned vs policies issued" className="lg:col-span-2">
              <ProviderBars rows={data.providers} />
            </Panel>
            <Panel title="Quote requests by product" subtitle="What customers are asking for">
              <Donut rows={data.quotes_by_category} />
            </Panel>
          </div>

          <SectionTitle>Payments &amp; channels</SectionTitle>
          <div className="mt-3 grid gap-4 lg:grid-cols-3">
            <Panel title="Payments by status" subtitle="Count of payment attempts">
              <Donut rows={data.payments_by_status} />
            </Panel>
            <Panel title="Collected by method" subtitle="Successful payments, by amount">
              <Donut rows={data.payments_by_method} metric="amount" />
            </Panel>
            <Panel title="Policies by channel" subtitle="Where policies came from">
              <Donut rows={data.policies_by_source} />
            </Panel>
          </div>

          <SectionTitle>Pipeline &amp; underwriting</SectionTitle>
          <div className="mt-3 grid gap-4 lg:grid-cols-3">
            <Panel title="Applications by status" subtitle="Started in this period">
              <HBars rows={data.applications_by_status} />
            </Panel>
            <Panel title="Leads by stage" subtitle="Created in this period">
              <HBars rows={data.leads_by_stage} color={COLORS.ink} />
            </Panel>
            <Panel title="Lead sources" subtitle="Where leads came from">
              <Donut rows={data.leads_by_source} />
            </Panel>
          </div>

          <SectionTitle>Claims, renewals &amp; delivery</SectionTitle>
          <div className="mt-3 grid gap-4 lg:grid-cols-3">
            <Panel title="Claims by status" subtitle="Reported in this period">
              <HBars rows={data.claims_by_status} />
            </Panel>
            <Panel title="Renewals" subtitle="All renewals, by status">
              <HBars rows={data.renewals_by_status} />
            </Panel>
            <Panel title="Sticker pipeline" subtitle="All stickers, by status">
              <HBars rows={data.stickers_by_status} color={COLORS.brandDeep} />
            </Panel>
          </div>

          <SectionTitle>Financing &amp; referrals</SectionTitle>
          <div className="mt-3 grid gap-4 lg:grid-cols-3">
            <Panel title="Financing requests" subtitle="Bidii Credit requests started in this period">
              <HBars rows={data.financing_by_status} />
            </Panel>
            <Panel title="Active financing" subtitle="All agreements, by status">
              <Donut rows={data.agreements_by_status} />
            </Panel>
            <Panel title="Affiliate commissions" subtitle="Earned in this period, by amount">
              <Donut rows={data.commissions_by_status} metric="amount" />
            </Panel>
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <Panel title="Referrals" subtitle="Referred in this period">
              <HBars rows={data.referrals_by_status} color={COLORS.info} />
            </Panel>
          </div>

          <p className="mt-6 text-xs text-ink-soft">
            Updated {new Date(data.generated_at).toLocaleString("en-KE")}. Days are counted in UTC.
          </p>
        </div>
      )}

      {/* <section className="mt-12 border-t border-neutral-border pt-8">
        <h2 className="mb-1 text-lg font-semibold">Shortcuts</h2>
        <p className="mb-6 text-sm text-ink-soft">Everything staff can manage, in one place.</p>
        <AdminQuickLinks />
      </section> */}
    </main>
  );
}

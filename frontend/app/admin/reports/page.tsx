"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import type { ProviderPerformance, ReportOverview } from "@/lib/types";

function formatKES(amount: string | number) {
  return `KES ${Number(amount).toLocaleString("en-KE", { maximumFractionDigits: 0 })}`;
}

function KpiCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <Card className="flex flex-col gap-1">
      <span className="text-xs font-medium uppercase tracking-wide text-ink-soft">{label}</span>
      <span className="font-display text-2xl font-extrabold">{value}</span>
      {sub && <span className="text-xs text-ink-soft">{sub}</span>}
    </Card>
  );
}

export default function ReportsOverviewPage() {
  const [data, setData] = useState<ReportOverview | null>(null);
  const [providers, setProviders] = useState<ProviderPerformance[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<ReportOverview>("/api/v1/admin/reports/overview"),
      api.get<ProviderPerformance[]>("/api/v1/admin/reports/provider-performance"),
    ])
      .then(([overview, perf]) => {
        setData(overview);
        setProviders(perf);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load reports"));
  }, []);

  if (error) return <main className="mx-auto max-w-5xl px-6 py-12 text-status-error">{error}</main>;
  if (!data) return <main className="mx-auto max-w-5xl px-6 py-12 text-ink-soft">Loading…</main>;

  const stickerChartData = Object.entries(data.stickers_by_status).map(([status, count]) => ({
    status: status.replace(/_/g, " "),
    count,
  }));

  const claimsChartData = Object.entries(data.claims.by_status).map(([status, count]) => ({
    status: status.replace(/_/g, " "),
    count,
  }));

  const providerChartData = providers.map((p) => ({
    name: p.name.length > 18 ? p.name.slice(0, 16) + "…" : p.name,
    quotes: p.quotes_returned,
    policies: p.policies_issued,
  }));

  return (
    <main className="mx-auto max-w-8xl px-6 py-12">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Management overview</h1>
        <a href="/api/v1/admin/reports/provider-performance/export.csv" target="_blank" rel="noreferrer">
          <Button variant="ghost">Export provider CSV</Button>
        </a>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard label="Customers" value={data.customers.total} sub={`+${data.customers.new_this_month} this month`} />
        <KpiCard label="Leads won" value={data.leads.won} sub={`of ${data.leads.total} total`} />
        <KpiCard
          label="Quote conversion"
          value={data.quotes.conversion_rate_pct !== null ? `${data.quotes.conversion_rate_pct}%` : "-"}
          sub={`${data.quotes.requests} requests`}
        />
        <KpiCard label="Active policies" value={data.policies.active} sub={`${data.policies.total} total`} />
        <KpiCard label="Active premium" value={formatKES(data.policies.total_active_premium)} />
        <KpiCard label="Revenue collected" value={formatKES(data.revenue.collected)} />
        <KpiCard label="Commission" value={formatKES(data.revenue.commission)} />
        <KpiCard label="Outstanding payments" value={data.revenue.outstanding_payment_count} />
        <KpiCard label="Open claims" value={data.claims.open} sub={`${data.claims.total} total`} />
        <KpiCard label="Renewals due" value={data.renewals.due} sub={`${data.renewals.renewed} renewed`} />
      </div>

      {providerChartData.length > 0 && (
        <section className="mt-10">
          <h2 className="text-lg font-semibold">Provider performance</h2>
          <Card className="mt-3 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={providerChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E3E5E9" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="quotes" fill="#FFC53D" name="Quotes returned" />
                <Bar dataKey="policies" fill="#1A1D21" name="Policies issued" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </section>
      )}

      {claimsChartData.length > 0 && (
        <section className="mt-10">
          <h2 className="text-lg font-semibold">Claims by status</h2>
          <Card className="mt-3 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={claimsChartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#E3E5E9" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="status" width={120} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#1A1D21" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </section>
      )}

      {stickerChartData.length > 0 && (
        <section className="mt-10">
          <h2 className="text-lg font-semibold">Sticker pipeline</h2>
          <Card className="mt-3 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stickerChartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#E3E5E9" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="status" width={120} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#E8A100" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </section>
      )}
    </main>
  );
}

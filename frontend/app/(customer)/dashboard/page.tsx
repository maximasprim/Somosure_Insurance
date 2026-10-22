"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { Bell, CalendarClock, CreditCard, FileText, LifeBuoy, Plus, ShieldAlert, ShieldCheck, User } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { ReferralCard } from "@/components/ReferralCard";
import { AffiliateCard } from "@/components/AffiliateCard";
import type { AppNotification, DashboardData } from "@/lib/types";

function formatKES(amount: string) {
  return `KES ${Number(amount).toLocaleString("en-KE", { maximumFractionDigits: 0 })}`;
}

/** "2026-10-16" -> "16 Oct 2026". Anything that is not a date is shown as it came. */
function formatDate(value: string) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

// --- building blocks -------------------------------------------------------------------

/** One number at the top of the page; it jumps to the section below. */
function SummaryTile({
  label,
  value,
  href,
  icon,
  attention = false,
}: {
  label: string;
  value: number;
  href: string;
  icon: ReactNode;
  attention?: boolean;
}) {
  const hot = attention && value > 0;
  return (
    <a
      href={href}
      className={`flex items-center gap-3 rounded-control border px-4 py-3 transition-colors hover:border-brand-deep ${
        hot ? "border-brand/60 bg-brand-tint/60" : "border-neutral-border bg-white"
      }`}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-neutral text-ink">{icon}</span>
      <span className="min-w-0">
        <span className="block font-display text-xl font-extrabold leading-tight text-ink">{value}</span>
        <span className="block text-xs leading-tight text-ink-soft">{label}</span>
      </span>
    </a>
  );
}

function Panel({
  id,
  title,
  subtitle,
  children,
}: {
  id: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <Card id={id} className="scroll-mt-24 !p-5 sm:!p-6">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {subtitle && <p className="mt-0.5 text-xs text-ink-soft">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </Card>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-control border border-dashed border-neutral-border px-4 py-5 text-sm text-ink-soft">{children}</div>
  );
}

function Skeleton() {
  return (
    <main className="mx-auto max-w-7xl animate-pulse px-4 py-8 sm:px-6 sm:py-10">
      <div className="h-8 w-48 rounded-control bg-neutral" />
      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-[68px] rounded-control bg-neutral" />
        ))}
      </div>
      <div className="mt-6 grid gap-5 lg:grid-cols-3">
        <div className="h-72 rounded-card bg-neutral lg:col-span-2" />
        <div className="h-72 rounded-card bg-neutral" />
      </div>
    </main>
  );
}

// --- page ------------------------------------------------------------------------------

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<DashboardData>("/api/v1/me/dashboard")
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load your dashboard"));
    api.get<AppNotification[]>("/api/v1/me/notifications").then(setNotifications).catch(() => {});
  }, []);

  if (error) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        <div className="rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>
      </main>
    );
  }

  if (!data) {
    return <Skeleton />;
  }

  // With nothing to flag, the side column would be an empty third of the page - let the main column use it.
  const hasSide = data.upcoming_renewals.length > 0 || data.outstanding_payments.length > 0 || notifications.length > 0;

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
      {/* Title and the places a customer goes next */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="font-display text-2xl font-extrabold text-ink">My dashboard</h1>
          <p className="mt-1 text-sm text-ink-soft">Your cover, applications and payments in one place.</p>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap">
          <Link href="/quote/motor" className="col-span-3 sm:col-span-1">
            <Button className="w-full gap-1.5">
              <Plus className="h-4 w-4" /> Get a quote
            </Button>
          </Link>
          <Link href="/claims">
            <Button variant="ghost" className="w-full gap-1.5 whitespace-nowrap !px-1.5 text-xs sm:!px-5 sm:text-sm">
              <ShieldAlert className="h-4 w-4" /> Claims
            </Button>
          </Link>
          <Link href="/support">
            <Button variant="ghost" className="w-full gap-1.5 whitespace-nowrap !px-1.5 text-xs sm:!px-5 sm:text-sm">
              <LifeBuoy className="h-4 w-4" /> Get support
            </Button>
          </Link>
          <Link href="/profile">
            <Button variant="ghost" className="w-full gap-1.5 whitespace-nowrap !px-1.5 text-xs sm:!px-5 sm:text-sm">
              <User className="h-4 w-4" /> Edit profile
            </Button>
          </Link>
        </div>
      </div>

      {/* At a glance */}
      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <SummaryTile label="Active policies" value={data.active_policies.length} href="#policies" icon={<ShieldCheck className="h-4 w-4" />} />
        <SummaryTile
          label="Pending applications"
          value={data.pending_applications.length}
          href="#applications"
          icon={<FileText className="h-4 w-4" />}
          attention
        />
        <SummaryTile
          label="Renewals due soon"
          value={data.upcoming_renewals.length}
          href="#renewals"
          icon={<CalendarClock className="h-4 w-4" />}
          attention
        />
        <SummaryTile
          label="Outstanding payments"
          value={data.outstanding_payments.length}
          href="#payments"
          icon={<CreditCard className="h-4 w-4" />}
          attention
        />
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-3">
        {/* Main column */}
        <div className={`flex flex-col gap-5 ${hasSide ? "lg:col-span-2" : "lg:col-span-3"}`}>
          <Panel id="policies" title="Active policies" subtitle="Cover that is in force right now.">
            {data.active_policies.length === 0 ? (
              <Empty>
                No active policies yet.{" "}
                <Link href="/quote/motor" className="font-medium text-ink underline underline-offset-2">
                  Get a quote
                </Link>{" "}
                to get covered.
              </Empty>
            ) : (
              <div className={`grid gap-4 sm:grid-cols-2 ${hasSide ? "" : "lg:grid-cols-3"}`}>
                {data.active_policies.map((p) => (
                  <div key={p.id} className="flex flex-col gap-3 rounded-control border border-neutral-border border-t-2 border-t-brand p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex min-w-0 items-center gap-2.5">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-tint text-ink">
                          <ShieldCheck className="h-4 w-4" />
                        </span>
                        <span className="truncate font-mono text-sm">{p.policy_number}</span>
                      </div>
                      <Badge tone="success">{p.status}</Badge>
                    </div>
                    <div>
                      <p className="text-xs text-ink-soft">Premium</p>
                      <p className="font-display text-xl font-extrabold text-ink">{formatKES(p.premium)}</p>
                    </div>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs text-ink-soft">
                        Valid {formatDate(p.start_date)} → {formatDate(p.end_date)}
                      </p>
                      {p.is_mock && <Badge tone="neutral">Demo policy</Badge>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel id="applications" title="Pending applications" subtitle="Applications we are still working on.">
            {data.pending_applications.length === 0 ? (
              <Empty>Nothing pending.</Empty>
            ) : (
              <ul className="divide-y divide-neutral-border">
                {data.pending_applications.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="flex min-w-0 items-center gap-2.5">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-neutral text-ink-soft">
                        <FileText className="h-4 w-4" />
                      </span>
                      <span className="truncate font-mono text-sm">{a.reference}</span>
                    </div>
                    <Badge tone="brand">{a.status.replace("_", " ")}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        {/* Side column: what needs attention */}
        {hasSide && (
        <div className="flex flex-col gap-5">
          {data.upcoming_renewals.length > 0 && (
            <Panel id="renewals" title="Renewals due soon" subtitle="Renew before the cover runs out.">
              <ul className="divide-y divide-neutral-border">
                {data.upcoming_renewals.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-sm">{p.policy_number}</p>
                      <p className="text-xs text-ink-soft">Expires {formatDate(p.end_date)}</p>
                    </div>
                    <Button size="md">Renew</Button>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {data.outstanding_payments.length > 0 && (
            <Panel id="payments" title="Outstanding payments" subtitle="Payments that still need your attention.">
              <ul className="divide-y divide-neutral-border">
                {data.outstanding_payments.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-sm">{p.reference}</p>
                      <p className="text-sm font-semibold text-ink">{formatKES(p.amount)}</p>
                    </div>
                    <Badge tone="error">{p.status}</Badge>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {notifications.length > 0 && (
            <Panel id="notifications" title="Notifications">
              <ul className="flex flex-col gap-3">
                {notifications.slice(0, 5).map((n) => (
                  <li key={n.id} className="flex gap-3 text-sm">
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-neutral text-ink-soft">
                      <Bell className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      {n.subject && <p className="font-medium text-ink">{n.subject}</p>}
                      <p className="break-words text-ink-soft">{n.body}</p>
                      <p className="mt-1 text-xs text-ink-soft">{new Date(n.created_at).toLocaleString()}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>
        )}
      </div>

      <ReferralCard />
      <AffiliateCard />
    </main>
  );
}

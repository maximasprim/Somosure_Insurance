"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { api, isLoggedIn } from "@/lib/api";
import { ReferralCard } from "@/components/ReferralCard";
import type { AppNotification, DashboardData } from "@/lib/types";

function formatKES(amount: string) {
  return `KES ${Number(amount).toLocaleString("en-KE", { maximumFractionDigits: 0 })}`;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      window.location.href = "/login";
      return;
    }
    api
      .get<DashboardData>("/api/v1/me/dashboard")
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load your dashboard"));
    api.get<AppNotification[]>("/api/v1/me/notifications").then(setNotifications).catch(() => {});
  }, []);

  if (error) {
    return (
      <main className="mx-auto max-w-7xl px-6 py-12">
        <div className="rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="mx-auto max-w-7xl px-6 py-12 text-ink-soft">Loading your dashboard…</main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-12">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">My dashboard</h1>
        <div className="flex gap-3">
          <Link href="/profile"><Button variant="ghost">Edit profile</Button></Link>
          <Link href="/claims"><Button variant="ghost">Claims</Button></Link>
          <Link href="/support"><Button variant="ghost">Get support</Button></Link>
        </div>
      </div>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Active policies</h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          {data.active_policies.map((p) => (
            <Card key={p.id} className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm">{p.policy_number}</span>
                {p.is_mock && <Badge tone="neutral">Demo policy</Badge>}
              </div>
              <p className="text-lg font-bold">{formatKES(p.premium)}</p>
              <p className="text-xs text-ink-soft">Valid {p.start_date} → {p.end_date}</p>
              <Badge tone="success">{p.status}</Badge>
            </Card>
          ))}
          {data.active_policies.length === 0 && <p className="text-ink-soft">No active policies yet.</p>}
        </div>
      </section>

      {data.upcoming_renewals.length > 0 && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold">Renewals due soon</h2>
          <div className="mt-3 flex flex-col gap-3">
            {data.upcoming_renewals.map((p) => (
              <Card key={p.id} className="flex items-center justify-between">
                <span>{p.policy_number} - expires {p.end_date}</span>
                <Button size="md">Renew</Button>
              </Card>
            ))}
          </div>
        </section>
      )}

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Pending applications</h2>
        <div className="mt-3 flex flex-col gap-3">
          {data.pending_applications.map((a) => (
            <Card key={a.id} className="flex items-center justify-between">
              <span className="font-mono text-sm">{a.reference}</span>
              <Badge tone="brand">{a.status.replace("_", " ")}</Badge>
            </Card>
          ))}
          {data.pending_applications.length === 0 && <p className="text-ink-soft">Nothing pending.</p>}
        </div>
      </section>

      {data.outstanding_payments.length > 0 && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold">Outstanding payments</h2>
          <div className="mt-3 flex flex-col gap-3">
            {data.outstanding_payments.map((p) => (
              <Card key={p.id} className="flex items-center justify-between">
                <span>{p.reference} - {formatKES(p.amount)}</span>
                <Badge tone="error">{p.status}</Badge>
              </Card>
            ))}
          </div>
        </section>
      )}

      {notifications.length > 0 && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold">Notifications</h2>
          <div className="mt-3 flex flex-col gap-2">
            {notifications.slice(0, 5).map((n) => (
              <Card key={n.id} className="text-sm">
                {n.subject && <p className="font-medium">{n.subject}</p>}
                <p className="text-ink-soft">{n.body}</p>
                <p className="mt-1 text-xs text-ink-soft">{new Date(n.created_at).toLocaleString()}</p>
              </Card>
            ))}
          </div>
        </section>
      )}

      <ReferralCard />
    </main>
  );
}

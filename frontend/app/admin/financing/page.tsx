"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { FinancingApplicationResult } from "@/lib/types";

const STATUS_TONE: Record<string, "success" | "neutral" | "error" | "brand"> = {
  approved: "success",
  rejected: "error",
  submitted: "brand",
};

export default function FinancingPortfolioPage() {
  const [applications, setApplications] = useState<FinancingApplicationResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<FinancingApplicationResult[]>("/api/v1/admin/financing/applications")
      .then(setApplications)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the financing portfolio"));
  }, []);

  if (error) return <main className="mx-auto max-w-4xl px-6 py-12 text-status-error">{error}</main>;

  const totalFinanced = applications
    .filter((a) => a.status === "approved")
    .reduce((sum, a) => sum + Number(a.financed_amount), 0);

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Bidii Credit financing portfolio</h1>
          <p className="mt-1 text-ink-soft">
            Total financed (approved): <strong>KES {totalFinanced.toLocaleString()}</strong>
          </p>
        </div>
        <Link href="/admin/financing/settings">
          <Button variant="ghost">Financing settings</Button>
        </Link>
      </div>

      <div className="mt-6 flex flex-col gap-3">
        {applications.map((a) => (
          <Card key={a.id} className="flex items-center justify-between">
            <div>
              <p className="font-mono text-sm">{a.reference}</p>
              <p className="text-xs text-ink-soft">
                Premium KES {Number(a.total_premium).toLocaleString()} · Financed KES{" "}
                {Number(a.financed_amount).toLocaleString()} over {a.term_months}mo at {a.interest_rate_monthly}%/month
              </p>
              {a.rejection_reason && <p className="mt-1 text-xs text-status-error">{a.rejection_reason}</p>}
            </div>
            <div className="flex items-center gap-3">
              <Badge tone={STATUS_TONE[a.status] ?? "neutral"}>{a.status}</Badge>
              <Link href={`/admin/financing/${a.id}`}>
                <Button variant="ghost">View details</Button>
              </Link>
            </div>
          </Card>
        ))}
        {applications.length === 0 && <p className="text-ink-soft">No financing applications yet.</p>}
      </div>
    </main>
  );
}
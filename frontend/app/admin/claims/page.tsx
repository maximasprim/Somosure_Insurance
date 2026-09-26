"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { Claim } from "@/lib/types";

const STATUS_TONE: Record<string, "success" | "neutral" | "error" | "brand"> = {
  reported: "neutral", documents_required: "neutral", submitted: "brand", under_review: "brand",
  insurer_review: "brand", approved: "success", settled: "success", rejected: "error", closed: "neutral",
};

// Mirrors ALLOWED_STAFF_TRANSITIONS in app/services/claim_service.py so
// the UI only offers valid next steps - the backend still enforces this
// independently.
const NEXT_STEPS: Record<string, string[]> = {
  reported: ["documents_required", "submitted"],
  documents_required: ["submitted"],
  submitted: ["under_review"],
  under_review: ["insurer_review", "approved", "rejected"],
  insurer_review: ["approved", "rejected"],
  approved: ["settled"],
  settled: ["closed"],
  rejected: ["closed"],
};

export default function AdminClaimsPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setClaims(await api.get<Claim[]>("/api/v1/admin/claims"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load claims - are you logged in as staff?");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function transition(claim: Claim, toStatus: string) {
    await api.post(`/api/v1/admin/claims/${claim.id}/transition`, { to_status: toStatus });
    load();
  }

  if (error) return <main className="mx-auto max-w-4xl px-6 py-12 text-status-error">{error}</main>;

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <h1 className="text-2xl font-bold">Claims</h1>
      <p className="mt-1 text-ink-soft">Review and progress claims through their lifecycle.</p>

      <div className="mt-6 flex flex-col gap-3">
        {claims.map((c) => (
          <Card key={c.id} className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-mono text-sm">{c.reference}</p>
                <p className="mt-1 text-xs text-ink-soft">{c.incident_description}</p>
                {c.provider_reference && <p className="mt-1 text-xs text-ink-soft">Insurer ref: {c.provider_reference}</p>}
              </div>
              <Badge tone={STATUS_TONE[c.status] ?? "neutral"}>{c.status.replace(/_/g, " ")}</Badge>
            </div>
            <div className="flex flex-wrap gap-2 border-t border-neutral-border pt-3">
              {(NEXT_STEPS[c.status] ?? []).map((next) => (
                <Button key={next} size="md" variant={next === "rejected" ? "ghost" : "primary"} onClick={() => transition(c, next)}>
                  {next.replace(/_/g, " ")}
                </Button>
              ))}
              {(NEXT_STEPS[c.status] ?? []).length === 0 && <span className="text-xs text-ink-soft">No further action needed</span>}
            </div>
          </Card>
        ))}
        {claims.length === 0 && <p className="text-ink-soft">No claims yet.</p>}
      </div>
    </main>
  );
}

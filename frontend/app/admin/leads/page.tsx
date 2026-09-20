"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { FunnelData, Lead } from "@/lib/types";

const STAGES = ["new", "contacted", "qualified", "quote", "negotiation", "won", "lost"] as const;

const STAGE_LABELS: Record<string, string> = {
  new: "New",
  contacted: "Contacted",
  qualified: "Qualified",
  quote: "Quote",
  negotiation: "Negotiation",
  won: "Won",
  lost: "Lost",
};

export default function LeadsPipelinePage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [funnel, setFunnel] = useState<FunnelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [leadsData, funnelData] = await Promise.all([
        api.get<Lead[]>("/api/v1/admin/leads"),
        api.get<FunnelData>("/api/v1/admin/leads/funnel"),
      ]);
      setLeads(leadsData);
      setFunnel(funnelData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the pipeline - are you logged in as staff?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function moveStage(lead: Lead, stage: string) {
    await api.patch(`/api/v1/admin/leads/${lead.id}`, { stage });
    load();
  }

  if (error) {
    return <main className="mx-auto max-w-7xl px-6 py-12"><div className="rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div></main>;
  }

  return (
    <main className="mx-auto max-w-8xl px-6 py-12">
      <h1 className="text-2xl font-bold">Lead pipeline</h1>

      {funnel && (
        <div className="mt-4 flex flex-wrap gap-3 text-sm text-ink-soft">
          {funnel.stages.map((s) => (
            <span key={s.stage}>
              {STAGE_LABELS[s.stage]}: <strong className="text-ink">{s.count}</strong>
            </span>
          ))}
        </div>
      )}

      {loading && <p className="mt-8 text-ink-soft">Loading…</p>}

      {!loading && (
        <div className="mt-8 grid gap-4 overflow-x-auto pb-4" style={{ gridTemplateColumns: `repeat(${STAGES.length}, minmax(220px, 1fr))` }}>
          {STAGES.map((stage) => (
            <div key={stage} className="flex flex-col gap-3">
              <h2 className="text-sm font-semibold text-ink-soft">
                {STAGE_LABELS[stage]} ({leads.filter((l) => l.stage === stage).length})
              </h2>
              <div className="flex flex-col gap-2">
                {leads
                  .filter((l) => l.stage === stage)
                  .map((lead) => (
                    <Card key={lead.id} className="p-3">
                      <Link href={`/admin/leads/${lead.id}`} className="font-medium hover:underline">
                        {lead.customer_name}
                      </Link>
                      <p className="text-xs text-ink-soft">{lead.customer_phone}</p>
                      {lead.product_interest && <Badge tone="brand" className="mt-2">{lead.product_interest}</Badge>}
                      <div className="mt-2 flex flex-wrap gap-1">
                        {STAGES.filter((s) => s !== stage).map((s) => (
                          <button
                            key={s}
                            onClick={() => moveStage(lead, s)}
                            className="rounded border border-neutral-border px-1.5 py-0.5 text-[10px] text-ink-soft hover:border-brand-deep hover:text-ink"
                          >
                            → {STAGE_LABELS[s]}
                          </button>
                        ))}
                      </div>
                    </Card>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}

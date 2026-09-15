"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { Lead, LeadActivity } from "@/lib/types";

export default function LeadDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [lead, setLead] = useState<Lead | null>(null);
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [leads, acts] = await Promise.all([
        api.get<Lead[]>("/api/v1/admin/leads"),
        api.get<LeadActivity[]>(`/api/v1/admin/leads/${id}/activities`),
      ]);
      setLead(leads.find((l) => l.id === id) ?? null);
      setActivities(acts);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load this lead");
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  async function addNote() {
    if (!note.trim()) return;
    await api.post(`/api/v1/admin/leads/${id}/activities`, { activity_type: "note", notes: note });
    setNote("");
    load();
  }

  if (error) return <main className="mx-auto max-w-2xl px-6 py-12 text-status-error">{error}</main>;
  if (!lead) return <main className="mx-auto max-w-2xl px-6 py-12 text-ink-soft">Loading…</main>;

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{lead.customer_name}</h1>
        <Badge tone="brand">{lead.stage}</Badge>
      </div>
      <p className="mt-1 text-ink-soft">{lead.customer_phone} · Source: {lead.source}</p>
      {lead.product_interest && <p className="mt-1 text-sm text-ink-soft">Interested in: {lead.product_interest}</p>}

      <Card className="mt-6 flex flex-col gap-3">
        <h2 className="font-semibold">Add a note</h2>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm"
          placeholder="Called, left voicemail, will follow up Thursday…"
        />
        <Button onClick={addNote} disabled={!note.trim()}>Add note</Button>
      </Card>

      <h2 className="mt-8 text-lg font-semibold">Activity</h2>
      <div className="mt-3 flex flex-col gap-3">
        {activities.map((a) => (
          <Card key={a.id} className="text-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium">{a.activity_type.replace("_", " ")}</span>
              <span className="text-xs text-ink-soft">{new Date(a.created_at).toLocaleString()}</span>
            </div>
            {a.notes && <p className="mt-1 text-ink-soft">{a.notes}</p>}
          </Card>
        ))}
        {activities.length === 0 && <p className="text-ink-soft">No activity yet.</p>}
      </div>
    </main>
  );
}

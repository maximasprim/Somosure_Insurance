"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api, getTokenUserId } from "@/lib/api";

interface TicketRow {
  id: string;
  reference: string;
  customer_name: string;
  category: string;
  subject: string;
  message: string;
  status: string;
  assigned_to_name: string | null;
}

const STATUSES = ["open", "assigned", "in_progress", "waiting_customer", "resolved", "closed"];

function toneFor(status: string): "success" | "error" | "brand" | "neutral" {
  if (status === "resolved" || status === "closed") return "success";
  if (status === "open") return "error";
  return "brand";
}

const selectClass = "rounded-control border border-neutral-border bg-white px-2 py-1.5 text-xs";

export default function AdminSupportPage() {
  const [tickets, setTickets] = useState<TicketRow[]>([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const myId = getTokenUserId();

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      setTickets(await api.get<TicketRow[]>(`/api/v1/admin/support-tickets?${params.toString()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tickets");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  async function updateStatus(t: TicketRow, newStatus: string) {
    await api.patch(`/api/v1/admin/support-tickets/${t.id}`, { status: newStatus });
    load();
  }

  async function assignToMe(t: TicketRow) {
    if (!myId) return;
    await api.patch(`/api/v1/admin/support-tickets/${t.id}`, { assigned_to_user_id: myId, status: t.status === "open" ? "assigned" : t.status });
    load();
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-2xl font-bold">Support tickets</h1>
      <p className="mt-1 text-ink-soft">Everything customers have submitted through the help center.</p>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <div className="mt-6 flex flex-col gap-1.5">
        <label className="text-sm font-medium text-ink">Status</label>
        <select
          className="w-fit rounded-control border border-neutral-border bg-white px-3 py-2 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4 flex flex-col gap-2">
        {loading && <p className="text-ink-soft">Loading…</p>}
        {!loading && tickets.length === 0 && <p className="text-ink-soft">No tickets found.</p>}
        {!loading &&
          tickets.map((t) => (
            <Card key={t.id} className="flex flex-col gap-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{t.subject}</h3>
                    <Badge tone={toneFor(t.status)}>{t.status.replace(/_/g, " ")}</Badge>
                    <Badge tone="neutral">{t.category}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-ink-soft">
                    {t.reference} · {t.customer_name} · {t.assigned_to_name ? `assigned to ${t.assigned_to_name}` : "unassigned"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {!t.assigned_to_name && (
                    <Button variant="ghost" onClick={() => assignToMe(t)}>
                      Assign to me
                    </Button>
                  )}
                  <select className={selectClass} value={t.status} onChange={(e) => updateStatus(t, e.target.value)}>
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <p className="text-sm text-ink-soft">{t.message}</p>
            </Card>
          ))}
      </div>
    </main>
  );
}

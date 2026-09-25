"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import type { SupportTicket } from "@/lib/types";

const CATEGORIES = ["quote", "payment", "policy", "claim", "renewal", "technical", "general"];

export default function SupportPage() {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [form, setForm] = useState({ category: "general", subject: "", message: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const data = await api.get<SupportTicket[]>("/api/v1/me/support-tickets");
    setTickets(data);
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/me/support-tickets", form);
      setForm({ category: "general", subject: "", message: "" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit your request");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-bold">Support</h1>
      <p className="mt-1 text-ink-soft">Tell us what's going on and our team will follow up.</p>

      <Card className="mt-6">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-ink">Category</label>
            <select
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <Input label="Subject" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} required />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-ink">Message</label>
            <textarea
              value={form.message}
              onChange={(e) => setForm({ ...form, message: e.target.value })}
              required
              rows={4}
              className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm"
            />
          </div>
          {error && <p className="text-sm text-status-error">{error}</p>}
          <Button type="submit" disabled={busy}>{busy ? "Submitting…" : "Submit request"}</Button>
        </form>
      </Card>

      <h2 className="mt-10 text-lg font-semibold">Your requests</h2>
      <div className="mt-3 flex flex-col gap-3">
        {tickets.map((t) => (
          <Card key={t.id} className="flex items-center justify-between">
            <div>
              <p className="font-medium">{t.subject}</p>
              <p className="text-xs text-ink-soft">{t.reference} · {t.category}</p>
            </div>
            <Badge tone={t.status === "resolved" || t.status === "closed" ? "success" : "brand"}>
              {t.status.replace("_", " ")}
            </Badge>
          </Card>
        ))}
        {tickets.length === 0 && <p className="text-ink-soft">No support requests yet.</p>}
      </div>
    </main>
  );
}
"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

const PARTNER_TYPES = ["car_dealer", "vehicle_importer", "employer", "sme", "bank", "sacco", "agent", "corporate"];

interface Partner {
  id: string;
  name: string;
  partner_type: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  is_active: boolean;
}

const selectClass =
  "rounded-control border border-neutral-border bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-deep/40 focus:border-brand-deep";

export default function AdminPartnersPage() {
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", partner_type: PARTNER_TYPES[0], contact_name: "", contact_email: "", contact_phone: "" });
  const [creating, setCreating] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setPartners(await api.get<Partner[]>("/api/v1/admin/partners"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load partners");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate() {
    if (!form.name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await api.post("/api/v1/admin/partners", {
        name: form.name,
        partner_type: form.partner_type,
        contact_name: form.contact_name || null,
        contact_email: form.contact_email || null,
        contact_phone: form.contact_phone || null,
      });
      setForm({ name: "", partner_type: PARTNER_TYPES[0], contact_name: "", contact_email: "", contact_phone: "" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create partner");
    } finally {
      setCreating(false);
    }
  }

  async function toggleActive(p: Partner) {
    try {
      await api.patch(`/api/v1/admin/partners/${p.id}`, { is_active: !p.is_active });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update partner");
    }
  }

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <h1 className="text-2xl font-bold">Partners</h1>
      <p className="mt-1 text-ink-soft">Car dealers, vehicle importers, employers, SACCOs, banks, and agents that refer business.</p>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <Card className="mt-6 flex flex-col gap-3">
        <h2 className="font-semibold">Add a partner</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-ink">Type</label>
            <select className={selectClass} value={form.partner_type} onChange={(e) => setForm({ ...form, partner_type: e.target.value })}>
              {PARTNER_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>
          <Input label="Contact name" value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} />
          <Input label="Contact email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} />
          <Input label="Contact phone" value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} />
        </div>
        <div>
          <Button onClick={handleCreate} disabled={creating}>
            {creating ? "Adding…" : "Add partner"}
          </Button>
        </div>
      </Card>

      <div className="mt-6 flex flex-col gap-3">
        {loading && <p className="text-ink-soft">Loading…</p>}
        {!loading && partners.length === 0 && <p className="text-ink-soft">No partners yet.</p>}
        {!loading &&
          partners.map((p) => (
            <Card key={p.id} className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{p.name}</h3>
                  <Badge tone="brand">{p.partner_type.replace(/_/g, " ")}</Badge>
                  {!p.is_active && <Badge tone="error">Inactive</Badge>}
                </div>
                <p className="mt-1 text-xs text-ink-soft">
                  {[p.contact_name, p.contact_email, p.contact_phone].filter(Boolean).join(" · ") || "No contact on file"}
                </p>
              </div>
              <Button variant="ghost" onClick={() => toggleActive(p)}>
                {p.is_active ? "Deactivate" : "Activate"}
              </Button>
            </Card>
          ))}
      </div>
    </main>
  );
}

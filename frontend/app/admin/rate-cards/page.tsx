"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

interface RateCardProvider {
  id: string;
  name: string;
  provider_type: string;
  status: string;
  integration_mode: string;
}

export default function RateCardProvidersPage() {
  const [providers, setProviders] = useState<RateCardProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    const data = await api.get<RateCardProvider[]>("/api/v1/admin/rate-cards/providers");
    setProviders(data);
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await api.post("/api/v1/admin/rate-cards/providers", { name: newName, provider_type: "insurer" });
      setNewName("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create provider");
    } finally {
      setCreating(false);
    }
  }

  async function activate(id: string) {
    setError(null);
    try {
      await api.post(`/api/v1/admin/rate-cards/providers/${id}/activate`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not activate - add at least one vehicle class first");
    }
  }

  return (
    <main className="mx-auto max-w-8xl px-6 py-12">
      <h1 className="text-2xl font-bold">Rate-card providers</h1>
      <p className="mt-1 text-ink-soft">
        Brokers/insurers priced from a configured rate card rather than a live API - e.g. AMACO and Pioneer Insurance
        Kenya. Add a new one when you receive a new broker&apos;s rate sheet; it stays inactive in customer quotes
        until it has at least one vehicle class configured.
      </p>

      {error && <div className="mt-4 rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}

      <Card className="mt-6 flex items-end gap-3">
        <div className="flex-1">
          <Input label="Add a broker" placeholder="e.g. Jubilee Insurance" value={newName} onChange={(e) => setNewName(e.target.value)} />
        </div>
        <Button onClick={handleCreate} disabled={creating}>
          {creating ? "Adding…" : "Add broker"}
        </Button>
      </Card>

      <div className="mt-6 flex flex-col gap-3">
        {loading && <p className="text-ink-soft">Loading…</p>}
        {!loading &&
          providers.map((p) => (
            <Card key={p.id} className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{p.name}</h3>
                  <Badge tone={p.status === "active" ? "success" : "neutral"}>{p.status}</Badge>
                </div>
                <p className="mt-1 text-xs text-ink-soft">{p.provider_type}</p>
              </div>
              <div className="flex gap-2">
                {p.status !== "active" && (
                  <Button variant="ghost" onClick={() => activate(p.id)}>
                    Activate
                  </Button>
                )}
                <Link href={`/admin/rate-cards/${p.id}`}>
                  <Button variant="ghost">Manage rates</Button>
                </Link>
              </div>
            </Card>
          ))}
        {!loading && providers.length === 0 && <p className="text-ink-soft">No rate-card providers yet.</p>}
      </div>
    </main>
  );
}

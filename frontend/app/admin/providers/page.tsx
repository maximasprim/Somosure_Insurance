"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

interface Provider {
  id: string;
  name: string;
  provider_type: string;
  integration_mode: string;
  status: string;
  supports_quote: boolean;
  supports_policy: boolean;
  supports_payment: boolean;
  supports_claims: boolean;
}

const statusTone: Record<string, "success" | "neutral" | "error"> = {
  active: "success",
  inactive: "neutral",
  maintenance: "error",
  manual_only: "neutral",
};

export default function AdminProvidersPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  async function load() {
    setLoading(true);
    const data = await api.get<Provider[]>("/api/v1/admin/providers");
    setProviders(data);
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    await api.post("/api/v1/admin/providers", { name: newName, provider_type: "insurer", integration_mode: "mock" });
    setNewName("");
    setCreating(false);
    load();
  }

  async function toggleStatus(provider: Provider) {
    const next = provider.status === "active" ? "inactive" : "active";
    await api.patch(`/api/v1/admin/providers/${provider.id}`, { status: next });
    load();
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="text-2xl font-bold">Insurance providers</h1>
      <p className="mt-1 text-ink-soft">
        Manage insurers and brokers integrated into the marketplace. Credentials are configured via environment
        secrets, never here.
      </p>

      <Card className="mt-6 flex items-end gap-3">
        <div className="flex-1">
          <Input label="Add a provider" placeholder="e.g. Britam" value={newName} onChange={(e) => setNewName(e.target.value)} />
        </div>
        <Button onClick={handleCreate} disabled={creating}>
          {creating ? "Adding…" : "Add provider"}
        </Button>
      </Card>

      <div className="mt-6 flex flex-col gap-3">
        {loading && <p className="text-ink-soft">Loading providers…</p>}
        {!loading &&
          providers.map((p) => (
            <Card key={p.id} className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{p.name}</h3>
                  <Badge tone={statusTone[p.status] ?? "neutral"}>{p.status}</Badge>
                  {p.integration_mode === "mock" && <Badge tone="neutral">Mock integration</Badge>}
                </div>
                <p className="mt-1 text-xs text-ink-soft">
                  Quote: {p.supports_quote ? "yes" : "no"} · Policy: {p.supports_policy ? "yes" : "no"} · Payment:{" "}
                  {p.supports_payment ? "yes" : "no"} · Claims: {p.supports_claims ? "yes" : "no"}
                </p>
              </div>
              <Button variant="ghost" onClick={() => toggleStatus(p)}>
                {p.status === "active" ? "Deactivate" : "Activate"}
              </Button>
            </Card>
          ))}
      </div>
    </main>
  );
}

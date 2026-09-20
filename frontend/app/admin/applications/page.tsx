"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { ApplicationResult } from "@/lib/types";

const statusTone: Record<string, "success" | "neutral" | "error" | "brand"> = {
  draft: "neutral",
  documents_required: "neutral",
  submitted: "brand",
  approved: "success",
  rejected: "error",
};

export default function AdminApplicationsPage() {
  const [applications, setApplications] = useState<ApplicationResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<ApplicationResult[]>("/api/v1/admin/applications");
      setApplications(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load applications - are you logged in as staff?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleApprove(id: string) {
    await api.post(`/api/v1/admin/applications/${id}/approve`, {});
    load();
  }

  return (
    <main className="mx-auto max-w-8xl px-6 py-12">
      <h1 className="text-2xl font-bold">Applications</h1>
      <p className="mt-1 text-ink-soft">Review submitted applications and approve them for payment and issuance.</p>

      {error && <div className="mt-6 rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}
      {loading && <p className="mt-6 text-ink-soft">Loading…</p>}

      <div className="mt-6 flex flex-col gap-3">
        {!loading &&
          applications.map((app) => (
            <Card key={app.id} className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{app.reference}</h3>
                  <Badge tone={statusTone[app.status] ?? "neutral"}>{app.status.replace("_", " ")}</Badge>
                </div>
                <p className="mt-1 text-xs text-ink-soft">Created {new Date(app.created_at).toLocaleString()}</p>
              </div>
              {app.status === "submitted" && (
                <Button onClick={() => handleApprove(app.id)}>Approve</Button>
              )}
            </Card>
          ))}
        {!loading && applications.length === 0 && !error && (
          <p className="text-ink-soft">No applications yet.</p>
        )}
      </div>
    </main>
  );
}

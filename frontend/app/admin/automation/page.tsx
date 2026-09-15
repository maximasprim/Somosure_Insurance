"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { AutomationRule, AutomationRun } from "@/lib/types";

export default function AutomationPage() {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [runs, setRuns] = useState<AutomationRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    try {
      const [r, ru] = await Promise.all([
        api.get<AutomationRule[]>("/api/v1/admin/automation/rules"),
        api.get<AutomationRun[]>("/api/v1/admin/automation/runs"),
      ]);
      setRules(r);
      setRuns(ru);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load automation data");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function toggleRule(rule: AutomationRule) {
    await api.patch(`/api/v1/admin/automation/rules/${rule.id}`, { is_active: !rule.is_active });
    load();
  }

  async function runAction(action: "run-due" | "scan-renewals" | "scan-abandoned-quotes") {
    setBusy(action);
    try {
      await api.post(`/api/v1/admin/automation/${action}`, {});
      await load();
    } finally {
      setBusy(null);
    }
  }

  if (error) return <main className="mx-auto max-w-4xl px-6 py-12 text-status-error">{error}</main>;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="text-2xl font-bold">Automation</h1>
      <p className="mt-1 text-ink-soft">
        Event → rule → action. No live scheduler is wired up yet, so the scans below run on demand - pointing a
        cron job at the same endpoints is all that changes later.
      </p>

      <div className="mt-6 flex flex-wrap gap-3">
        <Button onClick={() => runAction("run-due")} disabled={busy === "run-due"}>
          {busy === "run-due" ? "Running…" : "Run due automations"}
        </Button>
        <Button variant="ghost" onClick={() => runAction("scan-renewals")} disabled={busy === "scan-renewals"}>
          {busy === "scan-renewals" ? "Scanning…" : "Scan for renewals due"}
        </Button>
        <Button variant="ghost" onClick={() => runAction("scan-abandoned-quotes")} disabled={busy === "scan-abandoned-quotes"}>
          {busy === "scan-abandoned-quotes" ? "Scanning…" : "Scan for abandoned quotes"}
        </Button>
      </div>

      <h2 className="mt-10 text-lg font-semibold">Rules</h2>
      <div className="mt-3 flex flex-col gap-3">
        {rules.map((rule) => (
          <Card key={rule.id} className="flex items-center justify-between">
            <div>
              <p className="font-medium">{rule.name}</p>
              <p className="text-xs text-ink-soft">
                {rule.trigger_event} → {rule.action_type}
                {Object.keys(rule.conditions).length > 0 && ` (when ${JSON.stringify(rule.conditions)})`}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge tone={rule.is_active ? "success" : "neutral"}>{rule.is_active ? "active" : "inactive"}</Badge>
              <Button size="md" variant="ghost" onClick={() => toggleRule(rule)}>
                {rule.is_active ? "Disable" : "Enable"}
              </Button>
            </div>
          </Card>
        ))}
      </div>

      <h2 className="mt-10 text-lg font-semibold">Recent runs</h2>
      <div className="mt-3 flex flex-col gap-3">
        {runs.map((run) => (
          <Card key={run.id} className="text-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium">{run.trigger_event}</span>
              <Badge tone={run.status === "executed" ? "success" : run.status === "failed" ? "error" : "neutral"}>
                {run.status}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-ink-soft">
              {run.entity_type} {run.entity_id} · scheduled {new Date(run.scheduled_for).toLocaleString()}
            </p>
            {run.error && <p className="mt-1 text-xs text-status-error">{run.error}</p>}
          </Card>
        ))}
        {runs.length === 0 && <p className="text-ink-soft">No automation runs yet.</p>}
      </div>
    </main>
  );
}

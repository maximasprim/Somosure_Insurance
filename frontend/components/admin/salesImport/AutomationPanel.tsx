"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { api } from "@/lib/api";
import { AUTO_BASE, WEEKDAYS, when, type AutomationSettings, type AutomationState } from "@/lib/salesAutomation";

const FIELD = "rounded-control border border-neutral-border bg-white px-3 py-2 text-sm";
const TONE = { imported: "success", no_changes: "neutral", failed: "error" } as const;
const STATUS_LABEL = { imported: "Imported", no_changes: "No changes", failed: "Failed" } as const;

export function AutomationPanel({ refreshKey, onImported }: { refreshKey: number; onImported: () => void }) {
  const [state, setState] = useState<AutomationState | null>(null);
  const [form, setForm] = useState<AutomationSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api.get<AutomationState>(AUTO_BASE);
      setState(data);
      setForm(data.settings);
      setLoadError(null);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Could not load the settings.");
    }
  }

  useEffect(() => {
    load();
  }, [refreshKey]);

  if (loadError) return <p className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{loadError}</p>;
  if (!state || !form) return <TabSkeleton />;

  const settings = state.settings;
  const set = <K extends keyof AutomationSettings>(key: K, value: AutomationSettings[K]) => setForm((f) => (f ? { ...f, [key]: value } : f));

  async function save() {
    if (!form) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await api.put(AUTO_BASE, {
        sheet_url: form.sheet_url?.trim() || null,
        enabled: form.enabled,
        frequency: form.frequency,
        weekday: form.weekday,
        day_of_month: form.day_of_month,
        hour: form.hour,
        period_from: form.period_from || null,
        period_to: form.period_to || null,
        auto_post: form.auto_post,
      });
      setNotice("Saved.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save.");
    } finally {
      setSaving(false);
    }
  }

  async function runNow() {
    setRunning(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api.post<{ status: keyof typeof STATUS_LABEL; message: string }>(`${AUTO_BASE}/run-now`);
      if (res.status === "failed") setError(res.message);
      else setNotice(res.message);
      await load();
      if (res.status === "imported") onImported();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not run the import.");
    } finally {
      setRunning(false);
    }
  }

  async function resume() {
    setError(null);
    try {
      await api.post(`${AUTO_BASE}/resume`);
      setNotice("Automatic import resumed.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not resume.");
    }
  }

  const hasLink = Boolean(settings.sheet_url);

  return (
    <div className="flex flex-col gap-5">
      {settings.paused_reason && (
        <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-status-error/30 bg-status-error/5 px-5 py-4">
          <div>
            <p className="font-semibold">Automatic import is paused</p>
            <p className="mt-1 max-w-3xl text-sm text-ink-soft">{settings.paused_reason}</p>
          </div>
          <Button onClick={resume}>Resume automatic import</Button>
        </div>
      )}

      {error && <p role="alert" className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}
      {notice && <p role="status" className="rounded-control bg-status-success/10 px-4 py-2 text-sm text-status-success">{notice}</p>}

      <Card>
        <h2 className="text-lg font-semibold">Import from Google Sheets automatically</h2>
        <p className="mt-1 max-w-3xl text-sm text-ink-soft">
          The system reads the sheet on the schedule below and imports only what changed, exactly as if you had uploaded the workbook. Every import
          is kept as a version on the Versions tab, so you can go back to any of them.
        </p>

        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <div className="lg:col-span-2">
            <label htmlFor="sheet-url" className="text-sm font-medium">Google Sheet link</label>
            <input
              id="sheet-url"
              type="url"
              inputMode="url"
              autoComplete="off"
              placeholder="https://docs.google.com/spreadsheets/d/…"
              className={`${FIELD} mt-1 w-full`}
              value={form.sheet_url ?? ""}
              onChange={(e) => set("sheet_url", e.target.value)}
            />
            <p className="mt-1 text-xs text-ink-soft">
              In Google Sheets choose <strong>Share → General access → Anyone with the link → Viewer</strong>, then paste the sheet&apos;s address here.
              Whoever has the link can read the sheet, so share it only with people who should see it.
            </p>
          </div>

          <label className="flex items-start gap-2 lg:col-span-2">
            <input type="checkbox" className="mt-1" checked={form.enabled} onChange={(e) => set("enabled", e.target.checked)} />
            <span className="text-sm">
              <span className="font-medium">Import automatically</span>
              <span className="block text-ink-soft">Off keeps the link and settings but never pulls the sheet by itself. You can still use Run now.</span>
            </span>
          </label>

          <div>
            <label htmlFor="frequency" className="text-sm font-medium">How often</label>
            <select id="frequency" className={`${FIELD} mt-1 w-full`} value={form.frequency} onChange={(e) => set("frequency", e.target.value as AutomationSettings["frequency"])}>
              <option value="daily">Every day</option>
              <option value="weekly">Every week</option>
              <option value="monthly">Every month</option>
            </select>
          </div>

          <div className="flex flex-wrap gap-4">
            {form.frequency === "weekly" && (
              <div>
                <label htmlFor="weekday" className="text-sm font-medium">On</label>
                <select id="weekday" className={`${FIELD} mt-1`} value={form.weekday} onChange={(e) => set("weekday", Number(e.target.value))}>
                  {WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
                </select>
              </div>
            )}
            {form.frequency === "monthly" && (
              <div>
                <label htmlFor="dom" className="text-sm font-medium">On day</label>
                <select id="dom" className={`${FIELD} mt-1`} value={form.day_of_month} onChange={(e) => set("day_of_month", Number(e.target.value))}>
                  {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
            )}
            <div>
              <label htmlFor="hour" className="text-sm font-medium">At (Nairobi time)</label>
              <select id="hour" className={`${FIELD} mt-1`} value={form.hour} onChange={(e) => set("hour", Number(e.target.value))}>
                {Array.from({ length: 24 }, (_, h) => h).map((h) => <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>)}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-4 lg:col-span-2">
            <div>
              <label htmlFor="auto-from" className="text-sm font-medium">Import from</label>
              <input id="auto-from" type="month" className={`${FIELD} mt-1 block`} value={form.period_from ?? ""} onChange={(e) => set("period_from", e.target.value || null)} />
            </div>
            <div>
              <label htmlFor="auto-to" className="text-sm font-medium">Up to</label>
              <input id="auto-to" type="month" className={`${FIELD} mt-1 block`} value={form.period_to ?? ""} onChange={(e) => set("period_to", e.target.value || null)} />
            </div>
            <p className="max-w-md text-xs text-ink-soft">Optional. Same as on the Import tab: only these months are read, and older rows already in the system are left alone.</p>
          </div>

          <label className="flex items-start gap-2 lg:col-span-2">
            <input type="checkbox" className="mt-1" checked={form.auto_post} onChange={(e) => set("auto_post", e.target.checked)} />
            <span className="text-sm">
              <span className="font-medium">Also post new rows into the system</span>
              <span className="block text-ink-soft">
                After each import, create the customers, policies and payments for new rows that are complete. Rows with something missing wait on the Post to
                system tab. Leave this off to review before anything is posted.
              </span>
            </span>
          </label>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button onClick={save} disabled={saving}>{saving ? "Saving…" : "Save settings"}</Button>
          <Button variant="ghost" onClick={runNow} disabled={running || !hasLink}>{running ? "Importing…" : "Run now"}</Button>
          {!hasLink && <span className="text-xs text-ink-soft">Save a link first to use Run now.</span>}
        </div>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold">Status</h2>
        <dl className="mt-3 grid gap-4 text-sm md:grid-cols-3">
          <div>
            <dt className="text-ink-soft">Schedule</dt>
            <dd className="mt-0.5 font-medium">{settings.enabled ? settings.schedule_text : "Off"}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">Next import</dt>
            <dd className="mt-0.5 font-medium">{settings.paused_reason ? "On hold" : settings.enabled ? when(settings.next_run_at) : "-"}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">Last attempt</dt>
            <dd className="mt-0.5 font-medium">
              {settings.last_status ? <Badge tone={TONE[settings.last_status]}>{STATUS_LABEL[settings.last_status]}</Badge> : "None yet"}{" "}
              <span className="font-normal text-ink-soft">{when(settings.last_run_at)}</span>
            </dd>
          </div>
        </dl>
        {settings.last_status === "failed" && (
          <p role="alert" className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">
            {settings.last_message}
            {settings.consecutive_failures > 1 && ` (${settings.consecutive_failures} attempts in a row have failed.)`}
          </p>
        )}
      </Card>

      <Card>
        <h2 className="text-lg font-semibold">Recent attempts</h2>
        {state.runs.length === 0 ? (
          <p className="mt-2 text-sm text-ink-soft">Nothing has run yet.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="text-ink-soft">
                <tr><th className="py-2 pr-4 font-medium">When</th><th className="py-2 pr-4 font-medium">How</th><th className="py-2 pr-4 font-medium">Result</th><th className="py-2 font-medium">Details</th></tr>
              </thead>
              <tbody>
                {state.runs.map((r) => (
                  <tr key={r.id} className="border-t border-neutral-border align-top">
                    <td className="py-2 pr-4 whitespace-nowrap">{when(r.started_at)}</td>
                    <td className="py-2 pr-4 whitespace-nowrap">{r.trigger === "scheduled" ? "Scheduled" : "Run now"}</td>
                    <td className="py-2 pr-4"><Badge tone={TONE[r.status]}>{STATUS_LABEL[r.status]}</Badge></td>
                    <td className="py-2 text-ink-soft">{r.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

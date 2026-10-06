"use client";

import { Fragment, useEffect, useState } from "react";
import { AuditChanges } from "@/components/AuditChanges";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api, downloadFile } from "@/lib/api";
import type { AuditEntry, AuditFacets, AuditPage } from "@/lib/types";

const PAGE_SIZE = 50;

const VIEWS: { key: string; label: string; hint: string }[] = [
  { key: "change", label: "Changes", hint: "Every record created, edited or deleted" },
  { key: "event", label: "Events", hint: "Sign-ins, documents opened, exports, bulk actions" },
  { key: "request", label: "Requests", hint: "Every data-changing request with its outcome, including refused attempts" },
  { key: "", label: "Everything", hint: "All of the above" },
];

// Where each kind of record can be opened in the admin area.
const RECORD_ROUTES: Record<string, string> = {
  applications: "/admin/applications",
  financing_applications: "/admin/financing",
  customers: "/admin/customers",
  claims: "/admin/claims",
  policies: "/admin/policies",
  leads: "/admin/leads",
};

function toneFor(entry: AuditEntry): "success" | "error" | "brand" | "neutral" | "info" {
  if (entry.status_code && entry.status_code >= 400) return "error";
  if (entry.kind === "change") return entry.action === "deleted" ? "error" : entry.action === "created" ? "success" : "brand";
  if (entry.kind === "event") return "info";
  return "neutral";
}

function who(entry: AuditEntry): string {
  if (entry.actor_name) return entry.actor_name;
  if (entry.actor_type === "guest") return "Customer (not signed in)";
  return entry.actor_type === "system" ? "System" : "Unknown";
}

function startOfDay(d: string) {
  return new Date(`${d}T00:00:00`).toISOString();
}
function endOfDay(d: string) {
  return new Date(`${d}T23:59:59.999`).toISOString();
}

export default function AdminAuditPage() {
  const [view, setView] = useState("change");
  const [q, setQ] = useState("");
  const [actor, setActor] = useState("");
  const [entityType, setEntityType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [failedOnly, setFailedOnly] = useState(false);
  const [offset, setOffset] = useState(0);

  const [page, setPage] = useState<AuditPage | null>(null);
  const [facets, setFacets] = useState<AuditFacets | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  function buildParams(extra?: Record<string, string>) {
    const params = new URLSearchParams();
    if (view) params.set("kind", view);
    if (q.trim()) params.set("q", q.trim());
    if (actor.trim()) params.set("actor", actor.trim());
    if (entityType) params.set("entity_type", entityType);
    if (dateFrom) params.set("date_from", startOfDay(dateFrom));
    if (dateTo) params.set("date_to", endOfDay(dateTo));
    if (failedOnly) params.set("failed_only", "true");
    // Deep links from record screens (e.g. ?entity_id=...)
    const linked = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("entity_id") : null;
    if (linked) params.set("entity_id", linked);
    for (const [k, v] of Object.entries(extra ?? {})) params.set(k, v);
    return params;
  }

  async function load(nextOffset = offset) {
    setLoading(true);
    setError(null);
    try {
      const params = buildParams({ limit: String(PAGE_SIZE), offset: String(nextOffset) });
      setPage(await api.get<AuditPage>(`/api/v1/admin/audit?${params.toString()}`));
      setOffset(nextOffset);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load the audit trail");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, entityType, failedOnly, dateFrom, dateTo]);

  useEffect(() => {
    api.get<AuditFacets>("/api/v1/admin/audit/facets").then(setFacets).catch(() => undefined);
  }, []);

  async function exportCsv() {
    setExporting(true);
    setError(null);
    try {
      await downloadFile(`/api/v1/admin/audit/export.csv?${buildParams().toString()}`, "audit-trail.csv");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  const total = page?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <main className="mx-auto max-w-7xl px-3 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Audit trail</h1>
          <p className="mt-1 text-ink-soft">
            Who did what, when, to which record, and the reason given. Entries can&apos;t be edited or deleted.
          </p>
        </div>
        <Button variant="ghost" onClick={exportCsv} disabled={exporting}>
          {exporting ? "Preparing…" : "Export to CSV"}
        </Button>
      </div>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <div className="mt-6 flex flex-wrap gap-2">
        {VIEWS.map((v) => (
          <button
            key={v.label}
            type="button"
            title={v.hint}
            onClick={() => setView(v.key)}
            className={`rounded-full px-4 py-1.5 text-sm font-semibold ${
              view === v.key ? "bg-brand-deep text-white" : "bg-neutral text-ink-soft hover:text-ink"
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Input
          label="Search"
          placeholder="Reference, name, reason…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(0)}
        />
        <Input
          label="Done by"
          placeholder="Staff name or email"
          value={actor}
          onChange={(e) => setActor(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(0)}
        />
        <div className="flex flex-col gap-1.5">
          <label htmlFor="audit-entity" className="text-sm font-medium text-ink">Record type</label>
          <select
            id="audit-entity"
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm"
          >
            <option value="">All records</option>
            {(facets?.entity_types ?? []).map((t) => (
              <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <Button onClick={() => load(0)} disabled={loading}>Search</Button>
        </div>
        <Input label="From" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <Input label="To" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <label className="flex items-end gap-2 pb-2.5 text-sm text-ink">
          <input type="checkbox" checked={failedOnly} onChange={(e) => setFailedOnly(e.target.checked)} />
          Only refused / failed attempts
        </label>
      </div>

      <Card className="mt-6 overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="bg-neutral text-xs uppercase text-ink-soft">
            <tr>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3">Who</th>
              <th className="px-4 py-3">What</th>
              <th className="px-4 py-3">Record</th>
              <th className="px-4 py-3">Reason</th>
            </tr>
          </thead>
          <tbody>
            {(page?.items ?? []).map((entry) => {
              const route = entry.entity_type ? RECORD_ROUTES[entry.entity_type] : undefined;
              const expanded = openId === entry.id;
              return (
                <Fragment key={entry.id}>
                  <tr
                    className="cursor-pointer border-t border-neutral-border align-top hover:bg-neutral/40"
                    onClick={() => setOpenId(expanded ? null : entry.id)}
                  >
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-ink-soft">
                      {new Date(entry.occurred_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-ink">{who(entry)}</p>
                      {entry.actor_role && <p className="text-xs text-ink-soft">{entry.actor_role.replace(/_/g, " ")}</p>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={toneFor(entry)}>{entry.kind === "change" ? entry.action : entry.kind}</Badge>
                        {entry.status_code && entry.status_code >= 400 && <Badge tone="error">{entry.status_code}</Badge>}
                      </div>
                      <p className="mt-1 text-ink">{entry.summary ?? entry.action}</p>
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {entry.entity_type && <p className="text-ink-soft">{entry.entity_type.replace(/_/g, " ")}</p>}
                      {route && entry.entity_id ? (
                        <a
                          href={`${route}/${entry.entity_id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="font-semibold text-brand-deep hover:underline"
                        >
                          {entry.entity_label ?? "Open"}
                        </a>
                      ) : (
                        <p className="text-ink">{entry.entity_label ?? ""}</p>
                      )}
                    </td>
                    <td className="max-w-xs px-4 py-3 text-ink-soft">{entry.reason ?? "—"}</td>
                  </tr>
                  {expanded && (
                    <tr className="border-t border-neutral-border bg-neutral/30">
                      <td colSpan={5} className="px-4 py-4">
                        <div className="flex flex-col gap-4">
                          {entry.changes && Object.keys(entry.changes).length > 0 && <AuditChanges changes={entry.changes} />}
                          {entry.details && (
                            <pre className="overflow-x-auto rounded-control bg-white p-3 text-xs text-ink-soft">
                              {JSON.stringify(entry.details, null, 2)}
                            </pre>
                          )}
                          <dl className="grid gap-x-6 gap-y-1 text-xs text-ink-soft sm:grid-cols-2">
                            {entry.actor_email && <div><dt className="inline font-medium">Email: </dt><dd className="inline">{entry.actor_email}</dd></div>}
                            {entry.ip && <div><dt className="inline font-medium">IP address: </dt><dd className="inline">{entry.ip}</dd></div>}
                            {entry.method && <div><dt className="inline font-medium">Request: </dt><dd className="inline">{entry.method} {entry.path}</dd></div>}
                            {entry.duration_ms != null && <div><dt className="inline font-medium">Took: </dt><dd className="inline">{entry.duration_ms} ms</dd></div>}
                            {entry.user_agent && <div className="sm:col-span-2"><dt className="inline font-medium">Device: </dt><dd className="inline">{entry.user_agent}</dd></div>}
                            {entry.request_id && <div className="sm:col-span-2"><dt className="inline font-medium">Request ID: </dt><dd className="inline font-mono">{entry.request_id}</dd></div>}
                          </dl>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {!loading && (page?.items.length ?? 0) === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-ink-soft">Nothing matches these filters.</td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      <div className="mt-4 flex items-center justify-between text-sm text-ink-soft">
        <span>{loading ? "Loading…" : `${from}–${to} of ${total}`}</span>
        <div className="flex gap-2">
          <Button variant="ghost" disabled={offset === 0 || loading} onClick={() => load(Math.max(0, offset - PAGE_SIZE))}>
            ← Newer
          </Button>
          <Button variant="ghost" disabled={to >= total || loading} onClick={() => load(offset + PAGE_SIZE)}>
            Older →
          </Button>
        </div>
      </div>
    </main>
  );
}

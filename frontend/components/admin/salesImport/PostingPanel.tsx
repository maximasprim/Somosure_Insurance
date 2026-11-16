"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { api } from "@/lib/api";
import {
  HELD_LABELS,
  type HeldRow,
  POST_BASE,
  POST_FLAG_LABELS,
  type PostingOverview,
  type PostingStatus,
  type PostResult,
  type ProviderOption,
  type ReviewRow,
  type UnderwriterRow,
} from "@/lib/salesImport";

function UnderwriterLine({ row, providers, onSaved }: { row: UnderwriterRow; providers: ProviderOption[]; onSaved: () => void }) {
  const [choice, setChoice] = useState(row.provider_id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const changed = choice !== (row.provider_id ?? "") || (!!row.provider_id && row.source === "suggested");

  async function save(createNew: boolean) {
    setBusy(true);
    setError(null);
    try {
      await api.put(`${POST_BASE}/underwriters`, { underwriter: row.underwriter, provider_id: createNew ? null : choice || null, create_new: createNew });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr className="border-t border-neutral-border align-top">
      <td className="py-2 pr-3 font-medium">{row.underwriter}</td>
      <td className="pr-3">{row.rows} ({row.posted} posted)</td>
      <td className="pr-3">
        <select className="w-64 rounded-control border border-neutral-border bg-white px-2 py-1.5 text-xs" value={choice} onChange={(e) => setChoice(e.target.value)}>
          <option value="">Not linked</option>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>{p.name}{p.status !== "active" ? " (inactive)" : ""}</option>
          ))}
        </select>
      </td>
      <td className="pr-3">
        {row.source === "suggested" ? <Badge tone="brand">Suggested - confirm</Badge> : row.linked ? <Badge tone="success">Linked</Badge> : <Badge tone="error">Not linked</Badge>}
      </td>
      <td>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => save(false)} disabled={busy || !choice || !changed}>{row.source === "suggested" ? "Confirm" : "Save"}</Button>
          {!row.provider_id && <Button variant="ghost" onClick={() => save(true)} disabled={busy}>Create as new provider</Button>}
        </div>
        {error && <p className="mt-1 text-status-error">{error}</p>}
      </td>
    </tr>
  );
}

export function PostingPanel({ refreshKey, onPosted }: { refreshKey: number; onPosted: () => void }) {
  const [status, setStatus] = useState<PostingStatus | null>(null);
  const [unders, setUnders] = useState<UnderwriterRow[]>([]);
  const [providers, setProviders] = useState<ProviderOption[]>([]);
  const [held, setHeld] = useState<{ total: number; items: HeldRow[] } | null>(null);
  const [heldReason, setHeldReason] = useState("");
  const [review, setReview] = useState<{ total: number; items: ReviewRow[] } | null>(null);
  const [reviewCode, setReviewCode] = useState("");
  const [preview, setPreview] = useState<PostResult | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [danger, setDanger] = useState<{ policies: number; customers_created_by_workbook: number } | null>(null);
  const [confirmText, setConfirmText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [loaded, setLoaded] = useState(false);

  // One request for the whole tab; every section is set in the same step, so it draws complete.
  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (heldReason) params.set("reason", heldReason);
      if (reviewCode) params.set("code", reviewCode);
      const ov = await api.get<PostingOverview>(`${POST_BASE}/overview?${params.toString()}`);
      setStatus(ov.status);
      setUnders(ov.underwriters.underwriters);
      setProviders(ov.underwriters.providers);
      setHeld(ov.held);
      setReview(ov.review);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load");
    } finally {
      setLoaded(true);
    }
  }, [heldReason, reviewCode]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  async function run(dryRun: boolean) {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const result = await api.post<PostResult>(`${POST_BASE}/run?dry_run=${dryRun}`);
      if (dryRun) {
        setPreview(result);
      } else {
        setPreview(null);
        setDone(`Posted ${result.posted ?? 0} policies (${result.customers_created ?? 0} new customers). They now appear on the Policies, Payments and customer pages.`);
        await load();
        onPosted();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function autoLink() {
    setBusy(true);
    try {
      await api.post(`${POST_BASE}/underwriters/auto`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not link");
    } finally {
      setBusy(false);
    }
  }

  async function removeAll(dryRun: boolean) {
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<{ policies?: number; customers_created_by_workbook?: number; policies_removed?: number; policies_kept?: number; customers_removed?: number }>(
        `${POST_BASE}/unpost?dry_run=${dryRun}`
      );
      if (dryRun) {
        setDanger({ policies: r.policies ?? 0, customers_created_by_workbook: r.customers_created_by_workbook ?? 0 });
      } else {
        setDanger(null);
        setConfirmText("");
        setDone(`Removed ${r.policies_removed ?? 0} posted policies and ${r.customers_removed ?? 0} customers.${r.policies_kept ? ` ${r.policies_kept} were kept because they have activity added in the app.` : ""} The workbook ledger is unchanged.`);
        await load();
        onPosted();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const ready = status?.ready ?? 0;

  if (!loaded) return <TabSkeleton />;

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-5">
        <h2 className="text-lg font-semibold">Post the workbook into the system</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Every workbook row becomes the records the rest of the system already uses: a customer, a quote, an application, a policy and a payment. They appear on the
          Policies, Payments, Customers, Renewals, search and the dashboard like anything else, marked as coming from the workbook. The quote and application are
          reconstructed from the sheet (the manual records never captured them). Nothing is sent to anyone and no stickers or commissions are generated. Whatever a
          row is missing is flagged below for review - only a row with no premium, no dates at all, or an unlinked underwriter has to wait.
        </p>
        {status && (
          <div className="mt-4 grid gap-3 text-center md:grid-cols-4">
            {[
              ["Ready to post", status.ready],
              ["Waiting (can't be stored yet)", status.held_total],
              ["Already posted", status.posted],
              ["Match a platform policy", status.matched_to_platform_policies],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded-control bg-neutral/60 p-3">
                <div className="text-2xl font-bold">{value}</div>
                <div className="text-xs text-ink-soft">{label}</div>
              </div>
            ))}
          </div>
        )}
        {error && <p className="mt-3 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}
        {done && <p className="mt-3 rounded-control bg-status-success/10 px-4 py-2 text-sm text-status-success">{done}</p>}
      </Card>

      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">1. Link the underwriters to your providers</h3>
            <p className="text-xs text-ink-soft">
              &quot;MONARCH&quot; in the sheet and &quot;Monarch Insurance Company&quot; in your providers list are the same insurer; say so here once. Underwriters with no
              match can be created as new providers - created inactive, so they never receive quote requests. Correcting a link also corrects everything already posted.
            </p>
          </div>
          <Button variant="ghost" onClick={autoLink} disabled={busy}>Link the obvious matches</Button>
        </div>
        {unders.length === 0 ? (
          <p className="mt-3 text-sm text-ink-soft">Import a workbook first.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-ink-soft"><tr><th className="py-1 pr-3">In the sheet</th><th className="pr-3">Rows</th><th className="pr-3">Provider in the system</th><th className="pr-3">Status</th><th /></tr></thead>
              <tbody>
                {unders.map((u) => <UnderwriterLine key={`${u.underwriter}-${u.provider_id}-${u.source}`} row={u} providers={providers} onSaved={load} />)}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="p-5">
        <h3 className="text-sm font-semibold">2. Post</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="ghost" onClick={() => run(true)} disabled={busy}>Check what would be posted</Button>
        </div>
        {preview && (
          <div className="mt-4 rounded-control border border-neutral-border p-4 text-sm">
            <p><strong>{preview.to_post}</strong> workbook policies would be posted as customers, quotes, applications, policies and payments.</p>
            {Object.keys(preview.flags).length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-xs text-ink-soft">
                {Object.entries(preview.flags).map(([code, n]) => <li key={code}>{n} - {POST_FLAG_LABELS[code] ?? code}</li>)}
              </ul>
            )}
            {Object.keys(preview.held).length > 0 && (
              <p className="mt-2 text-xs text-ink-soft">Waiting: {Object.entries(preview.held).map(([c, n]) => `${n} ${HELD_LABELS[c] ?? c}`).join(" · ")}</p>
            )}
            <div className="mt-3 flex gap-2">
              <Button onClick={() => run(false)} disabled={busy || (preview.to_post ?? 0) === 0}>{busy ? "Posting…" : "Post to the system"}</Button>
              <Button variant="ghost" onClick={() => setPreview(null)} disabled={busy}>Cancel</Button>
            </div>
          </div>
        )}
        {ready === 0 && !preview && <p className="mt-3 text-sm text-ink-soft">Nothing is ready to post right now.</p>}
      </Card>

      <Card className="p-5">
        <h3 className="text-sm font-semibold">Waiting - fix in the sheet or link the underwriter ({held?.total ?? 0})</h3>
        <div className="mt-2">
          <select className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={heldReason} onChange={(e) => setHeldReason(e.target.value)}>
            <option value="">All reasons</option>
            {Object.entries(HELD_LABELS).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select>
        </div>
        {held && held.items.length > 0 ? (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-ink-soft"><tr><th className="py-1 pr-3">Client</th><th className="pr-3">Underwriter</th><th className="pr-3">Policy no.</th><th className="pr-3">Sheet row</th><th>Why it is waiting</th></tr></thead>
              <tbody>
                {held.items.map((h) => (
                  <tr key={h.id} className="border-t border-neutral-border">
                    <td className="py-1.5 pr-3 font-medium">{h.client_name}</td>
                    <td className="pr-3">{h.underwriter ?? "-"}</td>
                    <td className="pr-3 font-mono">{h.policy_number ?? "-"}</td>
                    <td className="pr-3">{h.sheet} row {h.row ?? "?"}</td>
                    <td>{h.reasons.map((r) => r.message).join("; ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-3 text-sm text-ink-soft">Nothing is waiting.</p>
        )}
      </Card>

      <Card className="p-5">
        <h3 className="text-sm font-semibold">Posted, but to review ({review?.total ?? 0})</h3>
        <p className="text-xs text-ink-soft">These are in the system already; the flag says what is missing or assumed. Fix the sheet (or add a phone on Sales &rarr; Customers) and the next import corrects the records.</p>
        {status && Object.keys(status.posted_flags).length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            <button className={`rounded-full border px-3 py-1 text-xs ${reviewCode === "" ? "border-brand-deep bg-brand-tint" : "border-neutral-border"}`} onClick={() => setReviewCode("")}>All</button>
            {Object.entries(status.posted_flags).map(([code, n]) => (
              <button key={code} className={`rounded-full border px-3 py-1 text-xs ${reviewCode === code ? "border-brand-deep bg-brand-tint" : "border-neutral-border"}`} onClick={() => setReviewCode(code)}>
                {POST_FLAG_LABELS[code] ?? code} ({n})
              </button>
            ))}
          </div>
        )}
        {review && review.items.length > 0 && (
          <ul className="mt-3 flex flex-col gap-1.5 text-sm">
            {review.items.map((r) => (
              <li key={r.id} className="flex flex-wrap items-baseline gap-2">
                <span className="font-medium">{r.client_name}</span>
                <span className="text-xs text-ink-soft">{r.policy_number} · {r.sheet} row {r.row ?? "?"}</span>
                {r.customer_id && <a className="text-xs text-brand-deep underline" href={`/admin/customers/${r.customer_id}`}>customer</a>}
                <span className="text-xs text-ink-soft">{r.flags.map((f) => POST_FLAG_LABELS[f.code] ?? f.code).join(" · ")}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="border-status-error/40 p-5">
        <h3 className="text-sm font-semibold">Undo</h3>
        <p className="text-xs text-ink-soft">
          Removes only what this page created (policies from the workbook, their quotes, applications, payments, and customers created from the workbook) - never
          anything the platform or your staff created. The workbook ledger stays, ready to post again. Super admin only.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={() => removeAll(true)} disabled={busy}>Check what would be removed</Button>
        </div>
        {danger && (
          <div className="mt-3 rounded-control border border-status-error/40 p-3 text-sm">
            <p>This would remove <strong>{danger.policies}</strong> posted policies and up to <strong>{danger.customers_created_by_workbook}</strong> customers created from the workbook.</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <input className="rounded-control border border-neutral-border px-2 py-1.5 text-xs" placeholder='Type REMOVE to confirm' value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
              <Button onClick={() => removeAll(false)} disabled={busy || confirmText !== "REMOVE"}>Remove</Button>
              <Button variant="ghost" onClick={() => setDanger(null)}>Cancel</Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

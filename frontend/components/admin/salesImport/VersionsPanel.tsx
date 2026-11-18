"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { api, downloadFile } from "@/lib/api";
import { SOURCE_LABEL, VERSIONS_BASE, sizeLabel, when, type ImportVersion, type RevertPreview } from "@/lib/salesAutomation";

const PAGE = 30;

function changeSummary(v: ImportVersion): string {
  const s = v.counts?.sales;
  if (!s) return "-";
  return `${s.new} new · ${s.updated} changed · ${s.missing} removed`;
}

export function VersionsPanel({ refreshKey, onReverted }: { refreshKey: number; onReverted: () => void }) {
  const [items, setItems] = useState<ImportVersion[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [target, setTarget] = useState<ImportVersion | null>(null);
  const [preview, setPreview] = useState<RevertPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [reverting, setReverting] = useState(false);

  async function load(limit = PAGE) {
    try {
      const data = await api.get<{ total: number; items: ImportVersion[] }>(`${VERSIONS_BASE}?limit=${limit}`);
      setItems(data.items);
      setTotal(data.total);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the versions.");
    }
  }

  useEffect(() => {
    load();
  }, [refreshKey]);

  async function openRevert(v: ImportVersion) {
    setTarget(v);
    setPreview(null);
    setPreviewError(null);
    setReason("");
    try {
      setPreview(await api.get<RevertPreview>(`${VERSIONS_BASE}/${v.id}/revert-preview`));
    } catch (e) {
      setPreviewError(e instanceof Error ? e.message : "Could not work out what would change.");
    }
  }

  function closeRevert() {
    if (!reverting) setTarget(null);
  }

  async function confirmRevert() {
    if (!target) return;
    setReverting(true);
    setPreviewError(null);
    try {
      const res = await api.post<{ version_no: number; restored: number; automation_paused: boolean }>(
        `${VERSIONS_BASE}/${target.id}/revert`,
        { reason: reason.trim() || null }
      );
      setTarget(null);
      setNotice(
        `Went back to version ${res.restored}; this is recorded as version ${res.version_no}.` +
          (res.automation_paused ? " Automatic import is paused - resume it on the Automation tab when you are ready." : "")
      );
      await load();
      onReverted();
    } catch (e) {
      setPreviewError(e instanceof Error ? e.message : "The revert did not complete.");
    } finally {
      setReverting(false);
    }
  }

  async function download(v: ImportVersion) {
    setError(null);
    try {
      await downloadFile(`${VERSIONS_BASE}/${v.id}/download`, `sales-report-v${v.version_no}.xlsx`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed.");
    }
  }

  if (!items && !error) return <TabSkeleton />;

  const s = preview?.counts.sales;
  const nothingToChange = preview && preview.changes_total === 0 && preview.missing_total === 0 && preview.posted_to_remove === 0;

  return (
    <div className="flex flex-col gap-5">
      {error && <p role="alert" className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}
      {notice && <p role="status" className="rounded-control bg-status-success/10 px-4 py-2 text-sm text-status-success">{notice}</p>}

      <Card>
        <h2 className="text-lg font-semibold">Import versions</h2>
        <p className="mt-1 max-w-3xl text-sm text-ink-soft">
          Every import - uploaded by hand or pulled from Google Sheets - is kept here with the exact workbook it came from. Reverting to a version sets
          the ledger back to what that workbook says. The revert is recorded as a new version, so nothing is lost and a revert can itself be reverted.
        </p>

        {!items || items.length === 0 ? (
          <p className="mt-4 text-sm text-ink-soft">No imports yet. The next one you run will appear here as version 1.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead className="text-ink-soft">
                <tr>
                  <th className="py-2 pr-4 font-medium">Version</th>
                  <th className="py-2 pr-4 font-medium">When (Nairobi)</th>
                  <th className="py-2 pr-4 font-medium">Source</th>
                  <th className="py-2 pr-4 font-medium">Sales in this import</th>
                  <th className="py-2 pr-4 font-medium">File</th>
                  <th className="py-2 font-medium"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {items.map((v) => (
                  <tr key={v.id} className="border-t border-neutral-border align-top">
                    <td className="py-3 pr-4 whitespace-nowrap font-semibold">
                      v{v.version_no} {v.is_current && <Badge tone="success" className="ml-1">Current</Badge>}
                    </td>
                    <td className="py-3 pr-4 whitespace-nowrap">{when(v.created_at)}</td>
                    <td className="py-3 pr-4">
                      <div>{SOURCE_LABEL[v.source]}{v.reverted_to_version_no != null && ` to v${v.reverted_to_version_no}`}</div>
                      <div className="text-xs text-ink-soft">{v.created_by_name ?? "-"}</div>
                      {v.note && <div className="mt-1 max-w-xs text-xs text-ink-soft">“{v.note}”</div>}
                    </td>
                    <td className="py-3 pr-4 whitespace-nowrap text-ink-soft">{changeSummary(v)}</td>
                    <td className="py-3 pr-4 text-ink-soft">
                      <div className="max-w-[14rem] truncate" title={v.filename ?? undefined}>{v.filename ?? "-"}</div>
                      <div className="text-xs">{sizeLabel(v.size_bytes)}</div>
                    </td>
                    <td className="py-3 text-right whitespace-nowrap">
                      <Button variant="ghost" className="px-3 py-1.5" onClick={() => download(v)}>Download</Button>{" "}
                      {!v.is_current && <Button variant="ghost" className="px-3 py-1.5" onClick={() => openRevert(v)}>Revert to this</Button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {items && total > items.length && (
          <div className="mt-4">
            <Button variant="ghost" onClick={() => load(items.length + PAGE)}>Show older versions ({total - items.length} more)</Button>
          </div>
        )}
      </Card>

      <Modal
        open={target !== null}
        onClose={closeRevert}
        title={target ? `Revert to version ${target.version_no}?` : ""}
        description={target ? `Imported ${when(target.created_at)}` : undefined}
      >
        {previewError && <p role="alert" className="mb-3 rounded-control bg-status-error/10 px-3 py-2 text-sm text-status-error">{previewError}</p>}
        {!preview && !previewError && <p className="text-sm text-ink-soft">Working out what would change…</p>}
        {preview && (
          <div className="flex flex-col gap-3 text-sm">
            {nothingToChange ? (
              <p className="rounded-control bg-brand-tint px-3 py-2">The ledger already matches this version, so nothing would change.</p>
            ) : (
              <ul className="list-disc space-y-1 pl-5">
                <li><strong>{preview.changes_total}</strong> row{preview.changes_total === 1 ? "" : "s"} set back to the values in this version{s ? ` (${s.updated} sales)` : ""}.</li>
                <li><strong>{preview.missing_total}</strong> row{preview.missing_total === 1 ? "" : "s"} that this version does not have will be marked “not in sheet”. They stay in the ledger.</li>
                {preview.posted_to_remove > 0 && (
                  <li className="text-status-error">
                    <strong>{preview.posted_to_remove}</strong> posted polic{preview.posted_to_remove === 1 ? "y" : "ies"} (with their payment, quote and application) will be removed. Policies that staff have since added a claim or renewal to are kept.
                  </li>
                )}
              </ul>
            )}
            <p className="text-ink-soft">
              Sales recorded by hand, follow-up notes, claims added in the app and the platform&apos;s own policies are not touched.
              {preview.will_pause_automation && " Automatic import will be paused, otherwise the next pull would bring today's sheet straight back."}
            </p>
            <div>
              <label htmlFor="revert-reason" className="font-medium">Why are you going back? <span className="font-normal text-ink-soft">(optional, kept with the version)</span></label>
              <textarea
                id="revert-reason"
                rows={2}
                maxLength={500}
                className="mt-1 w-full rounded-control border border-neutral-border bg-white px-3 py-2 text-sm"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </div>
            <div className="mt-1 flex justify-end gap-3">
              <Button variant="ghost" onClick={closeRevert} disabled={reverting}>Cancel</Button>
              <Button onClick={confirmRevert} disabled={reverting}>{reverting ? "Reverting…" : `Revert to version ${preview.version_no}`}</Button>
            </div>
          </div>
        )}
        {previewError && !preview && (
          <div className="mt-3 flex justify-end"><Button variant="ghost" onClick={closeRevert}>Close</Button></div>
        )}
      </Modal>
    </div>
  );
}

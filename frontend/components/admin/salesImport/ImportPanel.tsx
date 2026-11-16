"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { api, downloadFile, uploadFile } from "@/lib/api";
import { BASE, type EntryOptions, type ImportReport } from "@/lib/salesImport";
import { ReportView } from "./ReportView";

interface Batch {
  id: string;
  filename: string | null;
  created_at: string;
  counts: { sales?: { new: number; updated: number; missing: number } } | null;
}

export function ImportPanel({ onImported }: { onImported: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [exportYear, setExportYear] = useState("");
  // The period to import, remembered between visits so a weekly upload keeps "from January 2025".
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [postAfter, setPostAfter] = useState(false);
  const [sideLoaded, setSideLoaded] = useState(false);

  async function loadSide() {
    // History and the year list are fetched together and set together.
    const [b, o] = await Promise.allSettled([api.get<Batch[]>(`${BASE}/batches`), api.get<EntryOptions>(`${BASE}/entries/options`)]);
    if (b.status === "fulfilled") setBatches(b.value);
    if (o.status === "fulfilled") setYears(o.value.years);
    setSideLoaded(true);
  }

  useEffect(() => {
    loadSide();
    try {
      setFrom(window.localStorage.getItem("sales-import-from") ?? "");
      setTo(window.localStorage.getItem("sales-import-to") ?? "");
      setPostAfter(window.localStorage.getItem("sales-import-post") === "1");
    } catch {
      /* storage unavailable - the period simply is not remembered */
    }
  }, []);

  function changePeriod(which: "from" | "to", value: string) {
    (which === "from" ? setFrom : setTo)(value);
    try {
      window.localStorage.setItem(`sales-import-${which}`, value);
    } catch {
      /* ignore */
    }
    setReport(null); // a different period means a different check
    setDone(false);
  }

  function changePost(value: boolean) {
    setPostAfter(value);
    try {
      window.localStorage.setItem("sales-import-post", value ? "1" : "0");
    } catch {
      /* ignore */
    }
  }

  function periodQuery() {
    const params = new URLSearchParams();
    if (from) params.set("from_period", from);
    if (to) params.set("to_period", to);
    return params.toString();
  }

  function choose(f: File | null) {
    setFile(f);
    setReport(null);
    setDone(false);
    setError(null);
  }

  async function run(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await uploadFile<ImportReport>(`${BASE}/upload?dry_run=${dryRun}&post=${postAfter && !dryRun}&${periodQuery()}`, file);
      setReport(result);
      if (!dryRun) {
        setDone(true);
        onImported();
        loadSide();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    setError(null);
    try {
      await downloadFile(`${BASE}/export${exportYear ? `?years=${exportYear}` : ""}`, `sales-report-cleaned-${exportYear || "all"}.xlsx`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    }
  }

  if (!sideLoaded) return <TabSkeleton />;

  const sales = report?.counts.sales;
  const hasChanges = !!report && (report.counts.sales.new + report.counts.sales.updated + report.counts.sales.missing + report.counts.sales.restored +
    report.counts.claims.new + report.counts.claims.updated + report.counts.claims.missing +
    report.counts.ipf.new + report.counts.ipf.updated + report.counts.ipf.missing) > 0;

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-5">
        <h2 className="text-lg font-semibold">Upload the weekly report</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Use the same workbook you always do - all the year sheets, claims and IPF. The system checks it first and shows what would be added, changed or
          left out. Nothing is saved until you confirm. Uploading the same workbook again is safe: only differences are applied.
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-4 rounded-control bg-neutral/60 p-3">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="period-from">Import from</label>
            <input id="period-from" type="month" className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={from} onChange={(e) => changePeriod("from", e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="period-to">Up to (optional)</label>
            <input id="period-to" type="month" className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={to} onChange={(e) => changePeriod("to", e.target.value)} />
          </div>
          <div className="flex gap-2 text-xs">
            <button className="underline text-ink-soft" onClick={() => { changePeriod("from", "2025-01"); }}>From January 2025</button>
            <button className="underline text-ink-soft" onClick={() => { changePeriod("from", ""); changePeriod("to", ""); }}>Everything</button>
          </div>
          <p className="basis-full text-xs text-ink-soft">
            Only months inside this period are read and compared. Earlier months already in the system are not touched, even if they are in the file.
            {!from && !to && " No period chosen: the whole workbook is imported."}
          </p>
        </div>
        <label className="mt-3 flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={postAfter} onChange={(e) => changePost(e.target.checked)} />
          <span>
            After importing, also <strong>post new rows into the system</strong> (customers, quotes, policies, payments).
            <span className="block text-xs text-ink-soft">Better left off for the first big load: import, then review and post from the &quot;Post to system&quot; tab, where you can link underwriters and preview first. Rows already posted always follow the sheet.</span>
          </span>
        </label>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="text-sm"
            onChange={(e) => choose(e.target.files?.[0] ?? null)}
          />
          <Button onClick={() => run(true)} disabled={!file || busy}>
            {busy && !done ? "Working…" : "Check file"}
          </Button>
        </div>
        {error && <p className="mt-3 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}
      </Card>

      {report && !done && (
        <>
          {report.already_imported && (
            <p className="rounded-control bg-brand-tint px-4 py-2 text-sm">This exact file has been imported before. Importing it again changes nothing that is already up to date.</p>
          )}
          <ReportView report={report} />
          <Card className="sticky bottom-3 flex flex-wrap items-center justify-between gap-3 p-4 shadow-card">
            <p className="text-sm">
              {hasChanges ? (
                <>
                  Importing will add <strong>{sales?.new}</strong>, update <strong>{sales?.updated}</strong> and mark <strong>{sales?.missing}</strong> sales
                  rows as not in the sheet{report.counts.claims.new + report.counts.ipf.new > 0 ? ", plus new claims and IPF lines" : ""}.
                </>
              ) : (
                "The system already matches this file - nothing to import."
              )}
            </p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => choose(null)} disabled={busy}>
                Cancel
              </Button>
              <Button onClick={() => run(false)} disabled={busy || !hasChanges}>
                {busy ? "Importing…" : "Import now"}
              </Button>
            </div>
          </Card>
        </>
      )}

      {report && done && (
        <>
          <p className="rounded-control bg-status-success/10 px-4 py-2 text-sm text-status-success">
            Imported. The ledger now matches the sheet, and the sales, reports, renewals and customer pages read it alongside the platform&apos;s own data.
            {report.customer_links &&
              ` ${report.customer_links.linked_by_policy + report.customer_links.linked_by_phone + report.customer_links.linked_by_plate} policies were matched to existing customers.`}{" "}
            {report.posting?.posted && ` ${report.posting.posted.posted} policies were posted into the system.`}
            {report.posting?.resynced && report.posting.resynced.policies > 0 && ` ${report.posting.resynced.policies} posted policies were updated to follow the sheet.`}
            {report.posting?.error && ` ${report.posting.error}`}{" "}
            <a href="/admin/sales" className="underline">Open Sales</a> · <a href="#" className="underline" onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent("sales-import-tab", { detail: "post" })); }}>Post to the system</a>
            {report.customer_links && report.customer_links.clients_without_phone > 0 && (
              <> · <a href="/admin/sales?tab=customers" className="underline">{report.customer_links.clients_without_phone} clients still need a phone number</a></>
            )}
          </p>
          <ReportView report={report} />
        </>
      )}

      <Card className="p-5">
        <h2 className="text-lg font-semibold">Cleaned workbook</h2>
        <p className="mt-1 text-sm text-ink-soft">
          The same layout you use, with dates fixed (shown dd/mm/yyyy so Excel cannot swap day and month), names written one way, totals recalculated over every
          row, and a Review sheet listing what still needs a look. Keep working in this version and upload it as usual.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <select className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={exportYear} onChange={(e) => setExportYear(e.target.value)}>
            <option value="">All years</option>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
          <Button variant="ghost" onClick={download} disabled={years.length === 0}>
            Download cleaned workbook
          </Button>
          {years.length === 0 && <span className="text-xs text-ink-soft">Import a workbook first.</span>}
        </div>
      </Card>

      {batches.length > 0 && (
        <Card className="p-5">
          <h2 className="text-lg font-semibold">Import history</h2>
          <ul className="mt-3 flex flex-col divide-y divide-neutral-border text-sm">
            {batches.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>{b.filename ?? "workbook"}</span>
                <span className="text-xs text-ink-soft">
                  {b.counts?.sales ? `${b.counts.sales.new} new · ${b.counts.sales.updated} changed · ${b.counts.sales.missing} not in sheet · ` : ""}
                  {new Date(b.created_at).toLocaleString("en-KE")}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

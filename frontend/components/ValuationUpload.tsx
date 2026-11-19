"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { uploadFile } from "@/lib/api";

function formatDate(value: string) {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

/**
 * Shown on a policy that has only a one-month sticker because no valuation report was provided (comprehensive cover).
 * The customer uploads the report here; it is attached to the policy's own application, where the team sees it, and the
 * team then reconciles the premium and confirms the annual cover.
 */
export function ValuationUpload({ applicationId, dueDate }: { applicationId: string; dueDate: string | null }) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handle(file: File) {
    setBusy(true);
    setError(null);
    try {
      await uploadFile(`/api/v1/applications/${applicationId}/documents?document_type=valuation_report`, file);
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The upload did not go through. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div role="note" className="rounded-control border border-amber-300 bg-amber-50 px-3 py-2.5 text-xs text-amber-900">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="info">One-month sticker</Badge>
        {dueDate && <span className="font-medium">valid to {formatDate(dueDate)}</span>}
      </div>
      {done ? (
        <p className="mt-1.5">
          Thank you - we have your valuation report. Our team will confirm your annual cover and reconcile the premium to the actual value.
        </p>
      ) : (
        <>
          <p className="mt-1.5">
            Your sticker covers one month because we don&apos;t have a valuation report yet. Upload it before then to move to your annual
            comprehensive cover.
          </p>
          <label className="mt-1.5 inline-block cursor-pointer text-sm font-semibold text-brand-deep hover:underline">
            {busy ? "Checking…" : "Upload valuation report"}
            <input
              type="file"
              accept="application/pdf,image/jpeg,image/png"
              className="hidden"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handle(file);
                e.target.value = "";
              }}
            />
          </label>
        </>
      )}
      {error && <p className="mt-1 text-status-error">{error}</p>}
    </div>
  );
}

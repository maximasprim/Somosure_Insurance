"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

function requiredDocs(isCorporate: boolean) {
  return [
    { type: "application_form", label: "Filled financing application form" },
    { type: "logbook", label: "Original vehicle logbook" },
    isCorporate
      ? { type: "certificate_of_incorporation", label: "Certificate of incorporation" }
      : { type: "national_id", label: "Copy of national ID" },
    { type: "kra_pin", label: "KRA PIN certificate" },
    { type: "premium_quote", label: "Insurance premium quote" },
  ];
}

/**
 * Shown once a financing application has been created, so the customer can
 * attach the documents Bidii Credit needs alongside it (kept as its own
 * upload, separate from the insurance application's documents - see
 * FinancingDocument in the backend for why). This doesn't block payment;
 * it's a compliance checklist admin can see the state of on the financing
 * detail screen, not a gate the customer must clear here.
 */
export function FinancingDocumentsStep({ financingApplicationId, isCorporate }: { financingApplicationId: string; isCorporate: boolean }) {
  const [uploaded, setUploaded] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(docType: string, file: File) {
    setBusy(docType);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/v1/financing/applications/${financingApplicationId}/documents?document_type=${docType}`,
        { method: "POST", body: form }
      );
      if (!res.ok) throw new Error("Upload failed - please try again");
      setUploaded((prev) => ({ ...prev, [docType]: file.name }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="flex flex-col gap-4">
      <div>
        <h3 className="font-semibold">Bidii Credit documents</h3>
        <p className="mt-1 text-sm text-ink-soft">
          These are separate from your insurance application documents. PDF, JPEG, or PNG, up to 10MB each.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {requiredDocs(isCorporate).map((doc) => (
          <div
            key={doc.type}
            className="flex items-center justify-between rounded-control border border-neutral-border px-4 py-3"
          >
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">{doc.label}</span>
              {uploaded[doc.type] && <Badge tone="success">Uploaded</Badge>}
            </div>
            <label className="cursor-pointer text-sm font-semibold text-brand-deep hover:underline">
              {busy === doc.type ? "Uploading…" : uploaded[doc.type] ? "Replace" : "Choose file"}
              <input
                type="file"
                accept="application/pdf,image/jpeg,image/png"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleUpload(doc.type, file);
                }}
              />
            </label>
          </div>
        ))}
      </div>

      {error && <p className="text-sm text-status-error">{error}</p>}
    </Card>
  );
}
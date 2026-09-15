"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { api } from "@/lib/api";

const REQUIRED_DOCS = [
  { type: "national_id", label: "National ID" },
  { type: "logbook", label: "Vehicle logbook" },
  { type: "kra_pin", label: "KRA PIN certificate" },
];

export function DocumentUploadStep({
  applicationId,
  onSubmitted,
}: {
  applicationId: string;
  onSubmitted: () => void;
}) {
  const [uploaded, setUploaded] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleUpload(docType: string, file: File) {
    setBusy(docType);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/v1/applications/${applicationId}/documents?document_type=${docType}`,
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

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/api/v1/applications/${applicationId}/submit`, {});
      onSubmitted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit application");
    } finally {
      setSubmitting(false);
    }
  }

  const allUploaded = REQUIRED_DOCS.every((d) => uploaded[d.type]);

  return (
    <Card className="flex flex-col gap-5">
      <div>
        <h2 className="text-xl font-bold">Upload your documents</h2>
        <p className="mt-1 text-sm text-ink-soft">
          We need a few documents to complete your application. PDF, JPEG, or PNG, up to 10MB each.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {REQUIRED_DOCS.map((doc) => (
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

      <Button onClick={handleSubmit} disabled={!allUploaded || submitting} size="lg">
        {submitting ? "Submitting…" : "Submit application"}
      </Button>
    </Card>
  );
}

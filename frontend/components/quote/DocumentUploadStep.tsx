"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { api, uploadFile } from "@/lib/api";
import type { ChecklistItem, DocumentChecklist } from "@/lib/types";

// Fallback used only if the checklist can't be fetched - identical to the
// list this screen always used, so a backend hiccup degrades to the old
// behaviour instead of breaking the step.
const FALLBACK_ITEMS: ChecklistItem[] = [
  { type: "national_id", label: "National ID", description: "", tips: [], state: "missing", source: null },
  { type: "logbook", label: "Vehicle logbook", description: "", tips: [], state: "missing", source: null },
  { type: "kra_pin", label: "KRA PIN certificate", description: "", tips: [], state: "missing", source: null },
];

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPTED = ["application/pdf", "image/jpeg", "image/png"];

type UploadedState = { name: string; needsReview: boolean };

export function DocumentUploadStep({
  applicationId,
  onSubmitted,
}: {
  applicationId: string;
  onSubmitted: () => void;
}) {
  const [items, setItems] = useState<ChecklistItem[] | null>(null);
  const [uploaded, setUploaded] = useState<Record<string, UploadedState>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Ask the backend which documents this application needs and which are
  // already on file (identity documents a logged-in customer gave on an
  // earlier application are attached automatically - never asked twice).
  useEffect(() => {
    let cancelled = false;
    api
      .post<DocumentChecklist>(`/api/v1/applications/${applicationId}/documents/prepare`)
      .then((res) => {
        if (!cancelled) setItems(res.items);
      })
      .catch(() => {
        if (!cancelled) setItems(FALLBACK_ITEMS);
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId]);

  async function handleUpload(docType: string, file: File) {
    setErrors((prev) => ({ ...prev, [docType]: "" }));
    setError(null);

    // Instant, friendly checks before anything is sent.
    if (!ACCEPTED.includes(file.type)) {
      setErrors((prev) => ({ ...prev, [docType]: "Please choose a PDF, JPEG or PNG file." }));
      return;
    }
    if (file.size > MAX_BYTES) {
      setErrors((prev) => ({ ...prev, [docType]: "That file is over 10MB - please choose a smaller scan or photo." }));
      return;
    }

    setBusy(docType);
    try {
      const res = await uploadFile<{ status: string }>(
        `/api/v1/applications/${applicationId}/documents?document_type=${encodeURIComponent(docType)}`,
        file
      );
      setUploaded((prev) => ({ ...prev, [docType]: { name: file.name, needsReview: res.status === "needs_review" } }));
    } catch (e) {
      setErrors((prev) => ({ ...prev, [docType]: e instanceof Error ? e.message : "Upload failed - please try again" }));
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

  if (!items) {
    return (
      <Card>
        <p className="text-sm text-ink-soft">Getting your document list ready…</p>
      </Card>
    );
  }

  const isDone = (item: ChecklistItem) => item.state === "provided" || item.state === "auto" || !!uploaded[item.type];
  const allUploaded = items.every(isDone);
  const remaining = items.filter((i) => !isDone(i)).length;

  return (
    <Card className="flex flex-col gap-5">
      <div>
        <h2 className="text-xl font-bold">Upload your documents</h2>
        <p className="mt-1 text-sm text-ink-soft">
          PDF, JPEG, or PNG, up to 10MB each. We check each file as you upload it, so you&apos;ll know straight away if
          something needs another go.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {items.map((doc) => {
          const fresh = uploaded[doc.type];
          const onFile = doc.state === "provided" && !fresh;
          return (
            <div key={doc.type} className="rounded-control border border-neutral-border px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{doc.label}</span>
                  {fresh && <Badge tone="success">Uploaded</Badge>}
                  {onFile && (
                    <Badge tone="success">
                      {doc.source === "earlier_application" ? "Already on file from before" : "Already on file"}
                    </Badge>
                  )}
                </div>
                {!onFile && doc.state !== "auto" && (
                  <label className="shrink-0 cursor-pointer text-sm font-semibold text-brand-deep hover:underline">
                    {busy === doc.type ? "Checking…" : fresh ? "Replace" : "Choose file"}
                    <input
                      type="file"
                      accept="application/pdf,image/jpeg,image/png"
                      className="hidden"
                      disabled={busy !== null}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUpload(doc.type, file);
                        e.target.value = "";
                      }}
                    />
                  </label>
                )}
              </div>
              {doc.description && !fresh && !onFile && <p className="mt-1 text-xs text-ink-soft">{doc.description}</p>}
              {onFile && (
                <p className="mt-1 text-xs text-ink-soft">
                  We already have this from a previous application - nothing to upload.
                </p>
              )}
              {fresh?.needsReview && (
                <p className="mt-1 text-xs text-amber-700">
                  Uploaded, but it may be hard to read. If you can, replace it with a sharper copy - it gets approved
                  faster.
                </p>
              )}
              {errors[doc.type] && <p className="mt-1 text-sm text-status-error">{errors[doc.type]}</p>}
            </div>
          );
        })}
      </div>

      {error && <p className="text-sm text-status-error">{error}</p>}

      <Button onClick={handleSubmit} disabled={!allUploaded || submitting} size="lg">
        {submitting ? "Submitting…" : allUploaded ? "Submit application" : `Submit application (${remaining} document${remaining === 1 ? "" : "s"} to go)`}
      </Button>
    </Card>
  );
}

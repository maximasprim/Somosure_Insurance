"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { api, uploadFile } from "@/lib/api";
import type { ChecklistItem, DocumentChecklist } from "@/lib/types";

// Used only if the checklist can't be fetched - the same list this step always
// showed, with everything to upload, so a hiccup degrades to the old behaviour
// instead of breaking the step.
function fallbackItems(isCorporate: boolean): ChecklistItem[] {
  const item = (type: string, label: string): ChecklistItem => ({
    type,
    label,
    description: "",
    tips: [],
    state: "missing",
    source: null,
  });
  return [
    item("application_form", "Filled financing application form"),
    item("logbook", "Original vehicle logbook"),
    isCorporate ? item("certificate_of_incorporation", "Certificate of incorporation") : item("national_id", "Copy of national ID"),
    item("kra_pin", "KRA PIN certificate"),
    item("premium_quote", "Insurance premium quote"),
  ];
}

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPTED = ["application/pdf", "image/jpeg", "image/png"];

// Where a document that is already on file came from, in the customer's words.
const SOURCE_NOTE: Record<string, string> = {
  insurance_application: "Filled in from your insurance application",
  earlier_application: "Already on file from before",
  generated: "Prepared for you from the quote you selected",
  uploaded: "Uploaded",
};

type Fresh = { name: string; needsReview: boolean };

/**
 * The last page of a financing application. Everything Bidii Credit needs that
 * we already hold - the quote you chose, and the ID, KRA PIN and logbook you gave
 * for your insurance application - is filled in for you, and each one can be
 * replaced. Whatever is still missing (normally just the filled loan application
 * form) is marked as needed.
 *
 * Kept as its own upload, separate from the insurance application's documents
 * (see FinancingDocument in the backend). It doesn't block anything here: staff
 * see its state on the financing screen when they decide the application.
 */
export function FinancingDocumentsStep({
  financingApplicationId,
  isCorporate,
}: {
  financingApplicationId: string;
  isCorporate: boolean;
}) {
  const [items, setItems] = useState<ChecklistItem[] | null>(null);
  const [fresh, setFresh] = useState<Record<string, Fresh>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Fill in everything already on file (safe to repeat - it never duplicates).
  useEffect(() => {
    let cancelled = false;
    api
      .post<DocumentChecklist>(`/api/v1/financing/applications/${financingApplicationId}/documents/prepare`)
      .then((res) => {
        if (!cancelled) setItems(res.items);
      })
      .catch(() => {
        if (!cancelled) setItems(fallbackItems(isCorporate));
      });
    return () => {
      cancelled = true;
    };
  }, [financingApplicationId, isCorporate]);

  async function handleUpload(docType: string, file: File) {
    setErrors((prev) => ({ ...prev, [docType]: "" }));
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
        `/api/v1/financing/applications/${financingApplicationId}/documents?document_type=${encodeURIComponent(docType)}`,
        file
      );
      setFresh((prev) => ({ ...prev, [docType]: { name: file.name, needsReview: res.status === "needs_review" } }));
    } catch (e) {
      setErrors((prev) => ({ ...prev, [docType]: e instanceof Error ? e.message : "Upload failed - please try again" }));
    } finally {
      setBusy(null);
    }
  }

  if (!items) {
    return (
      <Card>
        <p className="text-sm text-ink-soft">Getting your financing documents ready…</p>
      </Card>
    );
  }

  const isDone = (item: ChecklistItem) => item.state !== "missing" || !!fresh[item.type];
  const stillNeeded = items.filter((i) => !isDone(i));

  return (
    <Card className="flex flex-col gap-4">
      <div>
        <h3 className="font-semibold">Bidii Credit documents</h3>
        <p className="mt-1 text-sm text-ink-soft">
          We&apos;ve filled in what we already have from your insurance application. You can replace any of it. PDF, JPEG or PNG, up
          to 10MB each.
        </p>
      </div>

      <div
        className={`rounded-control px-4 py-2.5 text-sm ${
          stillNeeded.length === 0 ? "bg-status-success/10 text-status-success" : "bg-brand-tint text-ink"
        }`}
      >
        {stillNeeded.length === 0
          ? "All your documents are in. Bidii Credit will review them and confirm your financing."
          : `Still needed from you: ${stillNeeded.map((i) => i.label.toLowerCase()).join(", ")}.`}
      </div>

      <div className="flex flex-col gap-3">
        {items.map((doc) => {
          const replaced = fresh[doc.type];
          const onFile = doc.state !== "missing" && !replaced;
          const needed = !isDone(doc);
          const canUpload = doc.state !== "auto";
          return (
            <div
              key={doc.type}
              className={`rounded-control border px-4 py-3 ${needed ? "border-brand-deep/50 bg-brand-tint/40" : "border-neutral-border"}`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{doc.label}</span>
                  {replaced && <Badge tone="success">{replaced.needsReview ? "Uploaded - please check" : "Uploaded"}</Badge>}
                  {onFile && <Badge tone="success">{SOURCE_NOTE[doc.source ?? "uploaded"] ?? "On file"}</Badge>}
                  {needed && <Badge tone="brand">Needed</Badge>}
                </div>
                {canUpload && (
                  <label className="shrink-0 cursor-pointer text-sm font-semibold text-brand-deep hover:underline">
                    {busy === doc.type ? "Uploading…" : needed ? "Choose file" : "Replace"}
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
              {needed && doc.description && <p className="mt-1 text-xs text-ink-soft">{doc.description}</p>}
              {replaced && (
                <p className="mt-1 text-xs text-ink-soft">
                  {replaced.name} will be used instead.
                  {replaced.needsReview ? " It may be hard to read - a sharper copy gets approved faster." : ""}
                </p>
              )}
              {errors[doc.type] && <p className="mt-1 text-sm text-status-error">{errors[doc.type]}</p>}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

"use client";

import { useEffect, useState } from "react";
import { FileCheck2 } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { DocumentRequirement, DocumentRequirements } from "@/lib/types";

/**
 * Shown right after quotes are generated - before the customer commits to
 * one and starts an application - so nobody reaches the upload step and
 * discovers they need a document they don't have to hand. Everything shown
 * comes from the backend (GET /api/v1/quotes/document-requirements), the
 * same list the upload screen and the upload checks use, so what we tell
 * people here can never disagree with what we later ask for.
 *
 * Purely informational: if the request fails it renders nothing, so it can
 * never block the quote flow.
 */
export function DocumentChecklistCard({ category }: { category: string }) {
  const [reqs, setReqs] = useState<DocumentRequirements | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<DocumentRequirements>(`/api/v1/quotes/document-requirements?category=${encodeURIComponent(category)}`)
      .then((res) => {
        if (!cancelled) setReqs(res);
      })
      .catch(() => {
        /* informational only */
      });
    return () => {
      cancelled = true;
    };
  }, [category]);

  if (!reqs) return null;

  const financingDocs = reqs.financing.documents.filter((d) => !d.system_provided);

  return (
    <Card className="flex flex-col gap-4 border-brand-deep/30">
      <div className="flex items-start gap-3">
        <FileCheck2 className="mt-0.5 h-5 w-5 shrink-0 text-brand-deep" aria-hidden />
        <div>
          <h2 className="text-base font-bold">Have these ready before you continue</h2>
          <p className="mt-1 text-sm text-ink-soft">
            You&apos;ll upload them in the next step. Keep clear softcopies ({reqs.accepted_formats}, up to {reqs.max_mb}MB
            each) on your phone or computer and it takes about two minutes.
          </p>
        </div>
      </div>

      <ul className="flex flex-col gap-3">
        {reqs.insurance.map((doc: DocumentRequirement) => (
          <li key={doc.type} className="rounded-control border border-neutral-border px-4 py-3">
            <p className="text-sm font-semibold text-ink">{doc.label}</p>
            <p className="mt-0.5 text-sm text-ink-soft">{doc.description}</p>
            {doc.tips.length > 0 && (
              <ul className="mt-1.5 list-disc pl-5 text-xs text-ink-soft">
                {doc.tips.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>

      <details className="text-sm text-ink-soft">
        <summary className="cursor-pointer font-semibold text-ink">Tips for a first-time approval</summary>
        <ul className="mt-2 list-disc pl-5 text-xs">
          {reqs.general_tips.map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
      </details>

      {financingDocs.length > 0 && (
        <details className="text-sm text-ink-soft">
          <summary className="cursor-pointer font-semibold text-ink">Planning to pay in instalments with Bidii Credit?</summary>
          <p className="mt-2 text-xs">{reqs.financing.note}</p>
          <p className="mt-2 text-xs font-medium text-ink">Bidii Credit also needs:</p>
          <ul className="mt-1 list-disc pl-5 text-xs">
            {financingDocs.map((doc) => (
              <li key={doc.type}>{doc.label}</li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}

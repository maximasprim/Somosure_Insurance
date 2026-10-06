"use client";

import { useEffect, useState } from "react";
import { AuditChanges } from "@/components/AuditChanges";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { AuditPage } from "@/lib/types";

/**
 * "Who did what to this record, when and why" - the audit trail filtered to
 * one record (or one customer). Shown on the application, financing and
 * customer screens.
 *
 * The audit trail is limited to management and super admins, so for anyone
 * else the request is refused and this renders nothing at all - it never
 * shows an error to people who aren't meant to see it.
 */
export function AuditTimeline({
  entityType,
  entityId,
  customerId,
  title = "Audit trail",
}: {
  entityType?: string;
  entityId?: string;
  customerId?: string;
  title?: string;
}) {
  const [page, setPage] = useState<AuditPage | null>(null);
  const [denied, setDenied] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ exclude_kind: "request", limit: "50" });
    if (entityType) params.set("entity_type", entityType);
    if (entityId) params.set("entity_id", entityId);
    if (customerId) params.set("customer_id", customerId);
    api
      .get<AuditPage>(`/api/v1/admin/audit?${params.toString()}`)
      .then((res) => !cancelled && setPage(res))
      .catch(() => !cancelled && setDenied(true));
    return () => {
      cancelled = true;
    };
  }, [entityType, entityId, customerId]);

  if (denied || !page) return null;

  return (
    <Card>
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 text-xs text-ink-soft">Every change to this record: who made it, when, and the reason given.</p>
      <div className="mt-4 flex flex-col gap-3">
        {page.items.map((entry) => (
          <div key={entry.id} className="border-l-2 border-neutral-border pl-3">
            <p className="text-sm text-ink">{entry.summary ?? entry.action}</p>
            <p className="mt-0.5 text-xs text-ink-soft">
              {entry.actor_name ?? (entry.actor_type === "guest" ? "Customer (not signed in)" : "System")}
              {entry.actor_role ? ` · ${entry.actor_role.replace(/_/g, " ")}` : ""} ·{" "}
              {new Date(entry.occurred_at).toLocaleString()}
            </p>
            {entry.reason && <p className="mt-0.5 text-sm text-ink-soft">Reason: &quot;{entry.reason}&quot;</p>}
            {entry.changes && Object.keys(entry.changes).length > 0 && (
              <>
                <button
                  type="button"
                  onClick={() => setOpen(open === entry.id ? null : entry.id)}
                  className="mt-1 text-xs font-semibold text-brand-deep hover:underline"
                >
                  {open === entry.id ? "Hide details" : "Show what changed"}
                </button>
                {open === entry.id && (
                  <div className="mt-2">
                    <AuditChanges changes={entry.changes} />
                  </div>
                )}
              </>
            )}
          </div>
        ))}
        {page.items.length === 0 && <p className="text-sm text-ink-soft">Nothing recorded yet.</p>}
        {page.total > page.items.length && (
          <a href={`/admin/audit?entity_id=${entityId ?? ""}`} className="text-xs font-semibold text-brand-deep hover:underline">
            See all {page.total} entries →
          </a>
        )}
      </div>
    </Card>
  );
}

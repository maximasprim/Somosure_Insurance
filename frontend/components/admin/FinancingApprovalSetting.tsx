"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

/**
 * The one switch that decides how Bidii Credit financing requests are approved:
 *   on  - staff approve or reject each request on the financing screen (default);
 *         it is a separate decision from the insurance application's approval.
 *   off - the credit provider's own instant answer stands, as it did before.
 * Saves on its own, so it doesn't touch the rates form below it.
 */
export function FinancingApprovalSetting({ canEdit }: { canEdit: boolean }) {
  const [value, setValue] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<{ require_staff_approval?: boolean }>("/api/v1/admin/financing/settings")
      .then((s) => setValue(s.require_staff_approval !== false))
      .catch(() => setValue(null));
  }, []);

  async function change(next: boolean) {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.patch<{ require_staff_approval?: boolean }>(
        "/api/v1/admin/financing/settings",
        { require_staff_approval: next },
        {
          reason: next
            ? "Financing requests now need a staff decision"
            : "Financing requests now follow the credit provider's instant decision",
        }
      );
      setValue(updated.require_staff_approval !== false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save this setting");
    } finally {
      setBusy(false);
    }
  }

  if (value === null) return null;

  return (
    <Card className="mt-6">
      <label className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={value}
          disabled={!canEdit || busy}
          onChange={(e) => change(e.target.checked)}
          className="mt-1 h-4 w-4 rounded border-neutral-border"
        />
        <span>
          <span className="block text-sm font-semibold text-ink">Staff approve every financing request</span>
          <span className="mt-0.5 block text-xs text-ink-soft">
            When on, a new Bidii Credit request waits as &quot;submitted&quot; until staff approve or reject it on the financing
            screen - separately from the insurance application. When off, the credit provider&apos;s instant answer stands.
          </span>
        </span>
      </label>
      {error && <p className="mt-2 text-sm text-status-error">{error}</p>}
    </Card>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { api } from "@/lib/api";
import { BASE, dmy, type EntryOptions, type Suggestion } from "@/lib/salesImport";

const keyOf = (s: Suggestion) => `${s.entry_id}|${s.field}|${s.suggested}`;

/** Date fixes the importer is fairly sure of, one per row, each accepted by a person. */
export function SuggestionsPanel({ refreshKey, onApplied }: { refreshKey: number; onApplied: () => void }) {
  const [years, setYears] = useState<number[]>([]);
  const [year, setYear] = useState("");
  const [items, setItems] = useState<Suggestion[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [optionsLoaded, setOptionsLoaded] = useState(false);
  const [itemsLoaded, setItemsLoaded] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setItems(await api.get<Suggestion[]>(`${BASE}/suggestions${year ? `?year=${year}` : ""}`));
      setPicked(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the suggestions");
    } finally {
      setItemsLoaded(true);
    }
  }, [year]);

  useEffect(() => {
    api
      .get<EntryOptions>(`${BASE}/entries/options`)
      .then((o) => setYears(o.years))
      .catch(() => undefined)
      .finally(() => setOptionsLoaded(true));
  }, [refreshKey]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  function toggle(s: Suggestion) {
    setPicked((prev) => {
      const next = new Set(prev);
      const k = keyOf(s);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  }

  async function apply(list: Suggestion[]) {
    if (list.length === 0) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const r = await api.post<{ applied: number; skipped: { reason: string }[] }>(`${BASE}/suggestions/apply`, {
        items: list.map((s) => ({ entry_id: s.entry_id, field: s.field, value: s.suggested })),
      });
      setMessage(`${r.applied} fix${r.applied === 1 ? "" : "es"} applied.${r.skipped.length ? ` ${r.skipped.length} skipped: ${r.skipped[0].reason}` : ""}`);
      await load();
      onApplied();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not apply");
    } finally {
      setBusy(false);
    }
  }

  const chosen = items.filter((s) => picked.has(keyOf(s)));

  if (!optionsLoaded || !itemsLoaded) return <TabSkeleton />;

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-5">
        <h2 className="text-lg font-semibold">Suggested fixes</h2>
        <p className="mt-1 text-sm text-ink-soft">
          For rows where a date looks like a year typo (for example expiry before the start date), the importer works out the most likely correction: the change
          that makes a one-year policy starting near the payment date. Nothing is changed until you accept it. An accepted fix is kept in the system even if the
          sheet still has the old date; correct the sheet when you can, and the note disappears. To undo a fix, change that date in the sheet and upload again.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <select className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={year} onChange={(e) => setYear(e.target.value)}>
            <option value="">All years</option>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <Button onClick={() => apply(chosen)} disabled={busy || chosen.length === 0}>
            Accept selected ({chosen.length})
          </Button>
          <Button variant="ghost" onClick={() => setPicked(new Set(items.map(keyOf)))} disabled={items.length === 0}>Select all</Button>
        </div>
        {message && <p className="mt-3 rounded-control bg-status-success/10 px-4 py-2 text-sm text-status-success">{message}</p>}
        {error && <p className="mt-3 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}
      </Card>

      {items.length === 0 ? (
        <p className="text-ink-soft">No suggested fixes waiting. Rows with date problems the importer cannot work out stay flagged on the Ledger tab.</p>
      ) : (
        items.map((s) => (
          <Card key={keyOf(s)} className="p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <label className="flex items-start gap-3">
                <input type="checkbox" className="mt-1" checked={picked.has(keyOf(s))} onChange={() => toggle(s)} />
                <span>
                  <span className="font-semibold">{s.client_name}</span>{" "}
                  <span className="text-xs text-ink-soft">{s.policy_number ?? "no policy number"} · {s.underwriter ?? "-"} · {s.sheet} row {s.row ?? "?"}</span>
                  <br />
                  <span className="text-sm">
                    Change the <strong>{s.label}</strong> from <strong>{dmy(s.current)}</strong> to <strong className="text-status-success">{dmy(s.suggested)}</strong>
                  </span>
                  <br />
                  <span className="text-xs text-ink-soft">
                    Now: start {dmy(s.start_date)} · expiry {dmy(s.expiry_date)} · paid {dmy(s.date_paid)}
                  </span>
                </span>
              </label>
              <Button variant="ghost" onClick={() => apply([s])} disabled={busy}>Accept</Button>
            </div>
          </Card>
        ))
      )}
      {items.length > 0 && <Badge tone="neutral">{items.length} waiting</Badge>}
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import { type Alias, BASE } from "@/lib/salesImport";

function AliasRow({ alias, onSaved }: { alias: Alias; onSaved: () => void }) {
  const [canonical, setCanonical] = useState(alias.canonical ?? "");
  const [branch, setBranch] = useState(alias.branch ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const changed = canonical !== (alias.canonical ?? "") || branch !== (alias.branch ?? "");

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.put(`${BASE}/aliases/${alias.id}`, { canonical, branch: alias.kind === "staff" ? branch : null, confirmed: true });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="grid items-center gap-2 border-t border-neutral-border py-2 md:grid-cols-[1fr_1fr_1fr_auto]">
      <span className="text-sm">
        <span className="font-mono text-xs">{alias.as_typed ?? alias.alias_key}</span>{" "}
        {!alias.confirmed && <Badge tone="brand">Check</Badge>}
      </span>
      <Input aria-label="Name used in the system" value={canonical} onChange={(e) => setCanonical(e.target.value)} placeholder={alias.kind === "staff" ? "Staff name" : "Insurer"} />
      {alias.kind === "staff" ? (
        <Input aria-label="Branch" value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="Branch" />
      ) : (
        <span />
      )}
      <Button variant={alias.confirmed && !changed ? "ghost" : "primary"} onClick={save} disabled={busy || (alias.confirmed && !changed)}>
        {alias.confirmed && !changed ? "Confirmed" : changed ? "Save" : "Confirm"}
      </Button>
      {error && <p className="text-xs text-status-error md:col-span-4">{error}</p>}
    </li>
  );
}

export function NamesPanel({ onChanged, refreshKey = 0 }: { onChanged: () => void; refreshKey?: number }) {
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [onlyCheck, setOnlyCheck] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [draft, setDraft] = useState({ kind: "staff", typed: "", canonical: "", branch: "" });

  const load = useCallback(async () => {
    try {
      setAliases(await api.get<Alias[]>(`${BASE}/aliases`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load names");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  async function reapply() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const r = await api.post<{ sales_rows: number; staff_rows: number; other_rows: number }>(`${BASE}/aliases/reapply`);
      setMessage(`Applied: ${r.sales_rows} sales rows updated (${r.staff_rows} with a different staff or branch), ${r.other_rows} claim/IPF rows.`);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not apply");
    } finally {
      setBusy(false);
    }
  }

  async function add() {
    setError(null);
    try {
      await api.post(`${BASE}/aliases`, draft);
      setDraft({ ...draft, typed: "", canonical: "", branch: "" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add");
    }
  }

  if (!loaded) return <TabSkeleton />;

  const shown = aliases.filter((a) => !onlyCheck || !a.confirmed);
  const groups: [string, Alias[]][] = [
    ["Underwriters", shown.filter((a) => a.kind === "underwriter")],
    ["Staff and branches", shown.filter((a) => a.kind === "staff")],
  ];

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-5">
        <h2 className="text-lg font-semibold">Names</h2>
        <p className="mt-1 text-sm text-ink-soft">
          The sheet spells the same insurer, staff member or branch in several ways. The importer matches them itself and lists each match here to confirm once.
          When you correct a name, press <strong>Apply to the ledger</strong> and every row follows; future uploads use your version.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={onlyCheck} onChange={(e) => setOnlyCheck(e.target.checked)} /> Only names still to check
          </label>
          <Button onClick={reapply} disabled={busy}>
            {busy ? "Applying…" : "Apply to the ledger"}
          </Button>
        </div>
        {message && <p className="mt-3 rounded-control bg-status-success/10 px-4 py-2 text-sm text-status-success">{message}</p>}
        {error && <p className="mt-3 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}
      </Card>

      {groups.map(([title, rows]) => (
        <Card key={title} className="p-5">
          <h3 className="text-sm font-semibold">{title} ({rows.length})</h3>
          {rows.length === 0 ? (
            <p className="mt-2 text-sm text-ink-soft">{onlyCheck ? "Nothing left to check." : "None yet - import a workbook."}</p>
          ) : (
            <ul className="mt-2">
              {rows.map((a) => (
                <AliasRow key={`${a.id}-${a.canonical}-${a.branch}-${a.confirmed}`} alias={a} onSaved={load} />
              ))}
            </ul>
          )}
        </Card>
      ))}

      <Card className="p-5">
        <h3 className="text-sm font-semibold">Add a spelling</h3>
        <p className="text-xs text-ink-soft">For a spelling that has not appeared yet. Type it exactly as it is (or will be) written in the sheet.</p>
        <div className="mt-3 grid items-end gap-3 md:grid-cols-5">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Kind</label>
            <select className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value })}>
              <option value="staff">Staff / branch</option>
              <option value="underwriter">Underwriter</option>
            </select>
          </div>
          <Input label="As typed in the sheet" value={draft.typed} onChange={(e) => setDraft({ ...draft, typed: e.target.value })} />
          <Input label={draft.kind === "staff" ? "Staff name" : "Insurer"} value={draft.canonical} onChange={(e) => setDraft({ ...draft, canonical: e.target.value })} />
          {draft.kind === "staff" ? <Input label="Branch" value={draft.branch} onChange={(e) => setDraft({ ...draft, branch: e.target.value })} /> : <span />}
          <Button onClick={add} disabled={!draft.typed.trim()}>Add</Button>
        </div>
      </Card>
    </div>
  );
}

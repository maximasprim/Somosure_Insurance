"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import { dmy, kes } from "@/lib/salesImport";
import { type CustomerStatus, type LinkResult, type NeedsPhoneRow, SALES_BASE } from "@/lib/salesSync";

const PAGE = 25;

function PhoneRow({ row, onSaved }: { row: NeedsPhoneRow; onSaved: (message: string) => void }) {
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<{ rows: number; linked_now: number }>(`${SALES_BASE}/customers/phone`, { client_key: row.client_key, phone });
      onSaved(`Saved for ${row.client_name} (${r.rows} polic${r.rows === 1 ? "y" : "ies"}).`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr className="border-t border-neutral-border align-top">
      <td className="py-2 pr-3 font-medium">{row.client_name}</td>
      <td className="pr-3">{row.policies}</td>
      <td className="pr-3">{row.sample_reg ?? "-"}</td>
      <td className="pr-3 text-right">{kes(row.premium)}</td>
      <td className="pr-3 whitespace-nowrap">{dmy(row.latest_expiry)}</td>
      <td>
        <div className="flex items-center gap-2">
          <input
            className="w-40 rounded-control border border-neutral-border bg-white px-2 py-1.5 text-xs"
            placeholder="0712 345 678"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
          <Button onClick={save} disabled={busy || phone.trim().length < 7}>{busy ? "…" : "Save"}</Button>
        </div>
        {error && <p className="mt-1 text-status-error">{error}</p>}
      </td>
    </tr>
  );
}

export function CustomersPanel({ refreshKey }: { refreshKey: number }) {
  const [status, setStatus] = useState<CustomerStatus | null>(null);
  const [preview, setPreview] = useState<{ create: boolean; result: LinkResult } | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<{ total: number; items: NeedsPhoneRow[] } | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await api.get<CustomerStatus>(`${SALES_BASE}/customers/status`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load");
    }
  }, []);

  const loadRows = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
      if (q) params.set("q", q);
      setRows(await api.get<{ total: number; items: NeedsPhoneRow[] }>(`${SALES_BASE}/customers/needs-phone?${params.toString()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load");
    }
  }, [q, offset]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus, refreshKey]);
  useEffect(() => {
    loadRows();
  }, [loadRows, refreshKey]);

  async function run(create: boolean, dryRun: boolean) {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const result = await api.post<LinkResult>(`${SALES_BASE}/customers/link?create=${create}&dry_run=${dryRun}`);
      if (dryRun) {
        setPreview({ create, result });
      } else {
        setPreview(null);
        setDone(
          `Done: ${result.linked_by_policy + result.linked_by_phone + result.linked_by_plate} policies matched to existing customers` +
            `${result.customers_created ? `, ${result.customers_created} customers created` : ""}.`
        );
        loadStatus();
        loadRows();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  // The counts and the list of clients waiting for a phone number are drawn together.
  if (!(status && rows) && !error) return <TabSkeleton />;

  const total = rows?.total ?? 0;

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-5">
        <h2 className="text-lg font-semibold">Workbook clients and customers</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Clients in the workbook can be matched to customers already in the system, so their policies, claims and renewals show on the customer&apos;s page.
          Matching uses the policy (if it is also a platform policy), then the phone number, then the number plate together with a similar name. Nothing is
          merged and no existing customer is changed. New customers are only created if you ask, and only for clients that have a phone number.
        </p>
        {status && (
          <div className="mt-4 grid gap-3 text-center md:grid-cols-4">
            {[
              ["Workbook clients", status.clients],
              ["Matched to a customer", status.linked],
              ["Not matched, have a phone", status.unlinked_with_phone],
              ["Not matched, no phone", status.unlinked_without_phone],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded-control bg-neutral/60 p-3">
                <div className="text-2xl font-bold">{value}</div>
                <div className="text-xs text-ink-soft">{label}</div>
              </div>
            ))}
          </div>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="ghost" onClick={() => run(false, true)} disabled={busy}>Check what would be matched</Button>
          <Button variant="ghost" onClick={() => run(true, true)} disabled={busy}>Check what would be created too</Button>
        </div>
        {error && <p className="mt-3 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}
        {done && <p className="mt-3 rounded-control bg-status-success/10 px-4 py-2 text-sm text-status-success">{done}</p>}

        {preview && (
          <div className="mt-4 rounded-control border border-neutral-border p-4 text-sm">
            <p className="font-semibold">{preview.create ? "If you create customers too" : "If you match to existing customers"}</p>
            <ul className="mt-2 list-disc pl-5">
              <li>{preview.result.linked_by_policy} policies match a platform policy&apos;s customer</li>
              <li>{preview.result.linked_by_phone} match one customer by phone number</li>
              <li>{preview.result.linked_by_plate} match one customer by number plate and a similar name</li>
              {preview.create ? (
                <li><strong>{preview.result.customers_created}</strong> new customers would be created (clients with a phone number that match nobody)</li>
              ) : (
                <li>{preview.result.policies_waiting_for_a_customer} more policies have a phone number but no customer ({preview.result.customers_that_would_be_created} customers could be created for them)</li>
              )}
              <li>{preview.result.clients_without_phone} clients have no phone number and cannot be created or matched by phone - add numbers below</li>
            </ul>
            <div className="mt-3 flex gap-2">
              <Button onClick={() => run(preview.create, false)} disabled={busy}>{busy ? "Working…" : preview.create ? "Match and create" : "Match now"}</Button>
              <Button variant="ghost" onClick={() => setPreview(null)} disabled={busy}>Cancel</Button>
            </div>
          </div>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="text-lg font-semibold">Clients waiting for a phone number</h2>
        <p className="mt-1 text-sm text-ink-soft">
          The 2025 and 2026 sheets have no phone column, so these clients cannot be matched or reminded. A number added here is kept on all their policies and
          holds until the sheet itself has one. (Adding a PHONE NO column to the sheet fills this in for everyone at once.)
        </p>
        <div className="mt-3 max-w-md">
          <Input label="Search by name" value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} />
        </div>
        {total === 0 ? (
          <p className="mt-4 text-sm text-ink-soft">Nobody is waiting for a phone number.</p>
        ) : (
          <>
            <div className="mt-4 flex items-center justify-between text-sm">
              <span><strong>{total}</strong> clients, most recent expiry first</span>
              <span className="flex items-center gap-2">
                <Button variant="ghost" onClick={() => setOffset(Math.max(0, offset - PAGE))} disabled={offset === 0}>Previous</Button>
                <span className="text-xs text-ink-soft">{offset + 1}-{Math.min(offset + PAGE, total)}</span>
                <Button variant="ghost" onClick={() => setOffset(offset + PAGE)} disabled={offset + PAGE >= total}>Next</Button>
              </span>
            </div>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-ink-soft">
                  <tr><th className="py-1 pr-3">Client</th><th className="pr-3">Policies</th><th className="pr-3">Reg / product</th><th className="pr-3 text-right">Premium</th><th className="pr-3">Latest expiry</th><th>Phone number</th></tr>
                </thead>
                <tbody>
                  {rows?.items.map((r) => (
                    <PhoneRow key={r.client_key} row={r} onSaved={(m) => { setDone(m); loadStatus(); loadRows(); }} />
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

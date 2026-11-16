"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import { dmy, kes } from "@/lib/salesImport";
import { FOLLOW_UP_LABELS, type RenewalItem, type RenewalPage, SALES_BASE, whatsappLink } from "@/lib/salesSync";

const PAGE = 50;

function DaysLeft({ days }: { days: number | null }) {
  if (days === null) return <span className="text-ink-soft">-</span>;
  if (days < 0) return <Badge tone="error">{Math.abs(days)}d overdue</Badge>;
  if (days <= 7) return <Badge tone="brand">{days}d left</Badge>;
  return <span className="text-ink-soft">{days}d left</span>;
}

function Row({ item, onSaved }: { item: RenewalItem; onSaved: () => void }) {
  const [status, setStatus] = useState(item.status);
  const [note, setNote] = useState(item.note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editable = item.source === "workbook";
  const changed = status !== item.status || note !== (item.note ?? "");
  const wa = whatsappLink(item.phone, `Hello ${item.client_name ?? ""}, your insurance${item.reg_no ? ` for ${item.reg_no}` : ""} is due for renewal${item.expiry_date ? ` on ${dmy(item.expiry_date)}` : ""}. Would you like us to prepare your renewal quote?`);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.put(`${SALES_BASE}/renewals/${item.id}`, { status: status === "due" ? null : status, note });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr className="border-t border-neutral-border align-top">
      <td className="py-2 pr-3 whitespace-nowrap">
        {dmy(item.expiry_date)}
        <br />
        <DaysLeft days={item.days_left} />
      </td>
      <td className="pr-3">
        <span className="font-medium">{item.client_name ?? "-"}</span>
        <br />
        <span className="text-ink-soft">{item.reg_no ?? "-"} · {item.underwriter ?? "-"}</span>
      </td>
      <td className="pr-3">
        {item.phone ? (
          <>
            <a className="text-brand-deep underline" href={`tel:${item.phone}`}>{item.phone}</a>
            {wa && (
              <>
                <br />
                <a className="text-brand-deep underline" href={wa} target="_blank" rel="noreferrer">WhatsApp</a>
              </>
            )}
          </>
        ) : (
          <span className="text-ink-soft">No phone yet</span>
        )}
      </td>
      <td className="pr-3 text-right">{kes(item.premium)}</td>
      <td className="pr-3">{[item.staff, item.branch].filter(Boolean).join(" · ") || "-"}</td>
      <td className="pr-3">
        <Badge tone={item.source === "platform" ? "info" : "neutral"}>{item.source === "platform" ? "Platform" : "Workbook"}</Badge>
      </td>
      <td className="min-w-[230px]">
        {editable ? (
          <div className="flex flex-col gap-1.5">
            <select className="rounded-control border border-neutral-border bg-white px-2 py-1.5 text-xs" value={status} onChange={(e) => setStatus(e.target.value)}>
              {["due", "contacted", "quoted", "renewed", "lost"].map((s) => <option key={s} value={s}>{FOLLOW_UP_LABELS[s]}</option>)}
            </select>
            <input
              className="rounded-control border border-neutral-border bg-white px-2 py-1.5 text-xs"
              placeholder="Note (what was said, when to call back)"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
            {changed && <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save"}</Button>}
            {error && <span className="text-status-error">{error}</span>}
          </div>
        ) : (
          <span>
            <Badge tone="neutral">{FOLLOW_UP_LABELS[item.status] ?? item.status}</Badge>{" "}
            <a className="text-brand-deep underline" href="/admin/renewals">manage</a>
          </span>
        )}
      </td>
    </tr>
  );
}

export function RenewalsPanel({ onNeedPhones, refreshKey = 0 }: { onNeedPhones: () => void; refreshKey?: number }) {
  const [days, setDays] = useState("60");
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [closed, setClosed] = useState(false);
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<RenewalPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ days, limit: String(PAGE), offset: String(offset) });
      if (source) params.set("source", source);
      if (status) params.set("status", status);
      if (q) params.set("q", q);
      if (closed) params.set("include_closed", "true");
      setPage(await api.get<RenewalPage>(`${SALES_BASE}/renewals?${params.toString()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load renewals");
    } finally {
      setLoading(false);
    }
  }, [days, source, status, q, closed, offset, refreshKey]);

  useEffect(() => {
    load();
  }, [load]);

  const total = page?.total ?? 0;
  const noPhone = page?.items.filter((i) => !i.phone).length ?? 0;
  const reset = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setOffset(0);
  };

  if (!page && !error) return <TabSkeleton />;

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <p className="mb-3 text-xs text-ink-soft">
          Policies due to renew, from the platform and from the workbook, soonest first. The last 30 days are included so nothing that just lapsed is lost. A
          workbook policy drops off when the same registration has a later policy in the sheet, or when you mark it renewed or lost. Nothing is sent
          automatically: use the phone or WhatsApp link to contact the client.
        </p>
        <div className="grid items-end gap-3 md:grid-cols-5">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Due within</label>
            <select className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={days} onChange={(e) => reset(setDays)(e.target.value)}>
              {[30, 60, 90, 180].map((d) => <option key={d} value={d}>{d} days</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">From</label>
            <select className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={source} onChange={(e) => reset(setSource)(e.target.value)}>
              <option value="">Both</option>
              <option value="platform">Platform</option>
              <option value="workbook">Workbook</option>
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Status</label>
            <select className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={status} onChange={(e) => reset(setStatus)(e.target.value)}>
              <option value="">Still to do</option>
              {["due", "contacted", "quoted", "renewed", "lost"].map((s) => <option key={s} value={s}>{FOLLOW_UP_LABELS[s]}</option>)}
            </select>
          </div>
          <div className="md:col-span-2">
            <Input label="Search client, registration, policy number, phone" value={q} onChange={(e) => reset(setQ)(e.target.value)} />
          </div>
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={closed} onChange={(e) => reset(setClosed)(e.target.checked)} /> Include renewed and lost
        </label>
      </Card>

      {error && <p className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
          <span>
            <strong>{total}</strong> renewals
            {noPhone > 0 && (
              <>
                {" "}· {noPhone} on this page have no phone number.{" "}
                <button className="text-brand-deep underline" onClick={onNeedPhones}>Add phone numbers</button>
              </>
            )}
          </span>
          <span className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => setOffset(Math.max(0, offset - PAGE))} disabled={offset === 0 || loading}>Previous</Button>
            <span className="text-xs text-ink-soft">{total ? `${offset + 1}-${Math.min(offset + PAGE, total)}` : "0"}</span>
            <Button variant="ghost" onClick={() => setOffset(offset + PAGE)} disabled={offset + PAGE >= total || loading}>Next</Button>
          </span>
        </div>
        {loading && !page ? (
          <p className="text-ink-soft">Loading…</p>
        ) : total === 0 ? (
          <p className="text-ink-soft">Nothing due in this window.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-ink-soft">
                <tr><th className="py-1 pr-3">Expires</th><th className="pr-3">Client</th><th className="pr-3">Contact</th><th className="pr-3 text-right">Premium</th><th className="pr-3">Staff · branch</th><th className="pr-3">From</th><th>Follow-up</th></tr>
              </thead>
              <tbody>
                {page?.items.map((item) => <Row key={`${item.source}-${item.id}-${item.status}-${item.note ?? ""}`} item={item} onSaved={load} />)}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

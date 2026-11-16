"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { TabSkeleton } from "@/components/admin/TabSkeleton";
import { api, downloadFile } from "@/lib/api";
import { CUSTOMER_LIST, type CustomerPage, sourceName } from "@/lib/customerList";
import { dmy, kes } from "@/lib/salesImport";

const PAGE = 50;

function daysUntil(iso: string | null): number | null {
  if (!iso) return null;
  const start = new Date(new Date().toDateString()).getTime();
  return Math.round((new Date(`${iso}T00:00:00`).getTime() - start) / 86400000);
}

function Select({ label, value, onChange, children }: { label: string; value: string; onChange: (v: string) => void; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-ink">{label}</label>
      <select className="rounded-control border border-neutral-border bg-white px-3 py-2 text-sm" value={value} onChange={(e) => onChange(e.target.value)}>
        {children}
      </select>
    </div>
  );
}

export default function AdminCustomersPage() {
  const [f, setF] = useState({ q: "", lead_source: "", has_phone: "", policy: "", sort: "newest" });
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<CustomerPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const query = useCallback(
    (withPaging: boolean) => {
      const params = new URLSearchParams();
      Object.entries(f).forEach(([k, v]) => v && params.set(k, v));
      if (withPaging) {
        params.set("limit", String(PAGE));
        params.set("offset", String(offset));
      }
      return params.toString();
    },
    [f, offset]
  );

  // The list, the counts above it and the filter choices come in one response, so the page draws complete.
  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setPage(await api.get<CustomerPage>(`${CUSTOMER_LIST}?${query(true)}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load customers");
    } finally {
      setBusy(false);
    }
  }, [query]);

  useEffect(() => {
    load();
  }, [load]);

  // typing in the search box waits a moment before asking, so each keystroke does not reload the list
  function typing(value: string) {
    setSearch(value);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      setF((prev) => ({ ...prev, q: value }));
      setOffset(0);
    }, 350);
  }

  const set = (key: keyof typeof f) => (value: string) => {
    setF((prev) => ({ ...prev, [key]: value }));
    setOffset(0);
  };

  async function download() {
    try {
      await downloadFile(`${CUSTOMER_LIST}/export?${query(false)}`, "customers.csv");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    }
  }

  if (!page && !error) {
    return (
      <main className="mx-auto max-w-8xl px-3 py-4">
        <h1 className="text-2xl font-bold">Customers</h1>
        <div className="mt-5"><TabSkeleton /></div>
      </main>
    );
  }

  const total = page?.total ?? 0;
  const stats = page?.stats;

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Customers</h1>
          <p className="mt-1 text-sm text-ink-soft">Everyone in the system - from the platform, WhatsApp, leads and the weekly report workbook - with what they hold.</p>
        </div>
        <Button variant="ghost" onClick={download}>Download as CSV</Button>
      </div>

      {stats && (
        <div className="mt-5 grid gap-3 text-center md:grid-cols-4">
          {[
            ["Customers", stats.customers],
            ["With an active policy", stats.with_active_policy],
            ["Without a phone number", stats.without_phone],
            ["From the weekly report", stats.from_workbook],
          ].map(([label, value]) => (
            <Card key={label as string} className="p-4">
              <div className="text-2xl font-bold">{Number(value).toLocaleString("en-KE")}</div>
              <div className="text-xs text-ink-soft">{label}</div>
            </Card>
          ))}
        </div>
      )}

      <Card className="mt-4 p-4">
        <div className="grid gap-3 md:grid-cols-5">
          <div className="md:col-span-2">
            <Input label="Search name, phone or email" value={search} onChange={(e) => typing(e.target.value)} />
          </div>
          <Select label="Where they came from" value={f.lead_source} onChange={set("lead_source")}>
            <option value="">Anywhere</option>
            {page?.sources.map((s) => <option key={s} value={s}>{sourceName(s)}</option>)}
          </Select>
          <Select label="Policies" value={f.policy} onChange={set("policy")}>
            <option value="">Any</option>
            <option value="active">With an active policy</option>
            <option value="expiring">Expiring in 60 days</option>
            <option value="expired">Only expired policies</option>
            <option value="none">No policy yet</option>
          </Select>
          <Select label="Phone number" value={f.has_phone} onChange={set("has_phone")}>
            <option value="">Any</option>
            <option value="true">Has a phone number</option>
            <option value="false">No phone number</option>
          </Select>
          <Select label="Sort by" value={f.sort} onChange={set("sort")}>
            <option value="newest">Newest first</option>
            <option value="name">Name</option>
            <option value="expiry">Next expiry</option>
            <option value="premium">Highest premium</option>
          </Select>
        </div>
      </Card>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <Card className={`mt-4 p-4 ${busy ? "opacity-70" : ""}`}>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
          <span><strong>{total.toLocaleString("en-KE")}</strong> customers match</span>
          <span className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => setOffset(Math.max(0, offset - PAGE))} disabled={offset === 0 || busy}>Previous</Button>
            <span className="text-xs text-ink-soft">{total ? `${offset + 1}-${Math.min(offset + PAGE, total)}` : "0"}</span>
            <Button variant="ghost" onClick={() => setOffset(offset + PAGE)} disabled={offset + PAGE >= total || busy}>Next</Button>
          </span>
        </div>
        {total === 0 ? (
          <p className="text-ink-soft">No customers match. Try clearing a filter.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-ink-soft">
                <tr>
                  <th className="py-1 pr-3">Customer</th><th className="pr-3">Phone</th><th className="pr-3">Email</th><th className="pr-3">Came from</th>
                  <th className="pr-3">Policies</th><th className="pr-3">Next expiry</th><th className="pr-3 text-right">Total premium</th><th>Added</th>
                </tr>
              </thead>
              <tbody>
                {page?.items.map((c) => {
                  const days = daysUntil(c.next_expiry);
                  return (
                    <tr key={c.id} className="border-t border-neutral-border hover:bg-neutral/50">
                      <td className="py-2 pr-3 font-medium">
                        <Link href={`/admin/customers/${c.id}`} className="text-brand-deep underline">{c.full_name}</Link>
                      </td>
                      <td className="pr-3">{c.phone ? c.phone : <Badge tone="neutral">No phone</Badge>}</td>
                      <td className="pr-3">{c.email ?? "-"}</td>
                      <td className="pr-3">
                        {sourceName(c.lead_source)}
                        {c.has_workbook && c.lead_source !== "workbook" && <> <Badge tone="neutral">+ workbook</Badge></>}
                      </td>
                      <td className="pr-3">
                        {c.policies === 0 ? <span className="text-ink-soft">None</span> : <>{c.active_policies} active <span className="text-ink-soft">of {c.policies}</span></>}
                      </td>
                      <td className="pr-3 whitespace-nowrap">
                        {c.next_expiry ? (
                          <>
                            {dmy(c.next_expiry)}{" "}
                            {days !== null && days <= 30 && <Badge tone={days <= 7 ? "brand" : "neutral"}>{days}d</Badge>}
                          </>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="pr-3 text-right">{c.policies ? kes(c.premium) : "-"}</td>
                      <td className="whitespace-nowrap">{dmy(c.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </main>
  );
}

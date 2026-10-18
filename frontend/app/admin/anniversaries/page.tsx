"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import {
  METHOD_LABEL,
  STRATEGY_LABEL,
  day,
  kes,
  type AnniversaryListItem,
  type AnniversarySettings,
  type CustomerLookup,
  type CustomerPlan,
  type PremiumPreview,
  type ProviderLite,
  type ScaleBand,
} from "@/lib/pricing";

const INPUT = "w-full rounded-control border border-neutral-border bg-white px-3 py-2 text-sm";
const BASE = "/api/v1/admin/anniversaries";

function errorText(e: unknown, fallback: string) {
  return e instanceof Error ? e.message : fallback;
}

export default function AnniversariesPage() {
  // --- configuration (finance / management roles)
  const [settings, setSettings] = useState<AnniversarySettings | null>(null);
  const [scales, setScales] = useState<ScaleBand[]>([]);
  const [providers, setProviders] = useState<ProviderLite[]>([]);
  const [canConfigure, setCanConfigure] = useState(true);
  const [table, setTable] = useState(""); // "" = the default table
  const [newBand, setNewBand] = useState({ up_to_days: "", percent_of_annual: "" });
  const [calc, setCalc] = useState({ annual: "", days: "", provider: "" });
  const [calcResult, setCalcResult] = useState<PremiumPreview | null>(null);

  // --- a customer's alignment (renewal roles)
  const [search, setSearch] = useState("");
  const [found, setFound] = useState<CustomerLookup[]>([]);
  const [plan, setPlan] = useState<CustomerPlan | null>(null);
  const [date, setDate] = useState("");
  const [notes, setNotes] = useState("");
  const [list, setList] = useState<AnniversaryListItem[]>([]);

  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadConfig = useCallback(async () => {
    try {
      const [s, sc, p] = await Promise.all([
        api.get<AnniversarySettings>(`${BASE}/settings`),
        api.get<ScaleBand[]>(`${BASE}/scales`),
        api.get<ProviderLite[]>(`${BASE}/providers`),
      ]);
      setSettings(s);
      setScales(sc);
      setProviders(p);
      setCanConfigure(true);
    } catch (e) {
      if (/insufficient permissions|403/i.test(errorText(e, ""))) setCanConfigure(false);
      else setError(errorText(e, "Could not load the anniversary settings"));
    }
  }, []);

  const loadList = useCallback(async () => {
    try {
      setList(await api.get<AnniversaryListItem[]>(BASE));
    } catch {
      setList([]);
    }
  }, []);

  useEffect(() => {
    loadConfig();
    loadList();
  }, [loadConfig, loadList]);

  async function run(work: () => Promise<unknown>, done?: string) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await work();
      if (done) setMessage(done);
    } catch (e) {
      setError(errorText(e, "That didn't work - please try again"));
    } finally {
      setBusy(false);
    }
  }

  const saveSettings = (patch: Partial<AnniversarySettings>) =>
    run(async () => {
      setSettings(await api.patch<AnniversarySettings>(`${BASE}/settings`, patch, { reason: "Anniversary alignment rules updated" }));
    }, "Saved.");

  const tableRows = scales.filter((s) => (table === "" ? s.provider_id === null : s.provider_id === table));

  const addBand = () =>
    run(async () => {
      await api.post(`${BASE}/scales`, {
        provider_id: table || null,
        up_to_days: Number(newBand.up_to_days),
        percent_of_annual: newBand.percent_of_annual,
      });
      setNewBand({ up_to_days: "", percent_of_annual: "" });
      await loadConfig();
    });

  const runCalc = () =>
    run(async () => {
      const q = new URLSearchParams({ annual_premium: calc.annual, term_days: calc.days });
      if (calc.provider) q.set("provider_id", calc.provider);
      setCalcResult(await api.get<PremiumPreview>(`${BASE}/preview?${q.toString()}`));
    });

  async function openPlan(customerId: string, previewDate?: string) {
    await run(async () => {
      const q = previewDate ? `?preview_date=${previewDate}` : "";
      const p = await api.get<CustomerPlan>(`${BASE}/customers/${customerId}${q}`);
      setPlan(p);
      setDate(previewDate ?? p.anniversary_date ?? p.suggested_anniversary ?? "");
      setNotes(p.notes ?? "");
    });
  }

  const doSearch = () =>
    run(async () => {
      setFound(await api.get<CustomerLookup[]>(`${BASE}/customers?search=${encodeURIComponent(search.trim())}`));
    });

  const saveAnniversary = () =>
    plan &&
    run(async () => {
      setPlan(await api.put<CustomerPlan>(`${BASE}/customers/${plan.customer_id}`, { anniversary_date: date, notes: notes || null }));
      await loadList();
    }, "Anniversary saved.");

  const removeAnniversary = () =>
    plan &&
    run(async () => {
      const cleared = await api.del<CustomerPlan>(`${BASE}/customers/${plan.customer_id}`);
      setPlan(cleared ?? plan);
      await loadList();
      await openPlan(plan.customer_id);
    }, "Anniversary removed.");

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <h1 className="text-2xl font-bold">Renewal anniversaries</h1>
      <p className="mt-1 max-w-3xl text-sm text-ink-soft">
        Renew all of a customer&apos;s covers on one date. Each cover&apos;s next renewal is cut to run until that anniversary, and from then on they all renew together. The
        premiums shown are estimates built from each policy&apos;s current premium - the insurer&apos;s renewal quote has the final figure.
      </p>
      {error && <p className="mt-3 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}
      {message && <p className="mt-3 text-sm text-status-success">{message}</p>}

      {/* ---- a customer's plan ---- */}
      <Card className="mt-6">
        <h2 className="text-sm font-semibold">Line up a customer&apos;s covers</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <input className={`${INPUT} max-w-xs`} placeholder="Customer name or phone" value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search.trim().length >= 2 && doSearch()} />
          <Button onClick={doSearch} disabled={busy || search.trim().length < 2}>
            Find
          </Button>
        </div>
        {found.length > 0 && (
          <ul className="mt-3 divide-y divide-neutral-border/60 rounded-control border border-neutral-border">
            {found.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
                <span>
                  <span className="font-medium text-ink">{c.full_name}</span> <span className="text-xs text-ink-soft">{c.phone}</span>
                  <span className="ml-2 text-xs text-ink-soft">{c.active_policies} active {c.active_policies === 1 ? "cover" : "covers"}</span>
                  {c.anniversary_date && <Badge className="ml-2" tone="success">Anniversary {day(c.anniversary_date)}</Badge>}
                </span>
                <button type="button" className="text-xs font-semibold text-brand-deep hover:underline" onClick={() => openPlan(c.id)}>
                  Open
                </button>
              </li>
            ))}
          </ul>
        )}

        {plan && (
          <div className="mt-5 border-t border-neutral-border/60 pt-4">
            <p className="text-sm font-semibold text-ink">{plan.customer_name}</p>
            {!plan.enabled && <p className="mt-1 text-xs text-status-error">Anniversary alignment is switched off, so it isn&apos;t shown on the renewals screen.</p>}
            {plan.policies.length === 0 && <p className="mt-2 text-sm text-ink-soft">This customer has no active covers that haven&apos;t expired.</p>}
            {plan.using_suggestion && plan.policies.length > 0 && (
              <p className="mt-2 rounded-control bg-brand-tint px-3 py-2 text-xs text-ink">
                No anniversary is saved yet. This previews the suggested one - the latest expiry among their covers, so none of the others has to run longer than a year.
              </p>
            )}

            <div className="mt-3 grid items-end gap-3 sm:grid-cols-[auto_1fr_auto_auto]">
              <label className="text-xs text-ink-soft">
                Common anniversary
                <input className={`${INPUT} mt-1`} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
              </label>
              <label className="text-xs text-ink-soft">
                Notes
                <input className={`${INPUT} mt-1`} value={notes} maxLength={500} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. agreed with the customer by phone" />
              </label>
              <Button variant="ghost" disabled={busy || !date} onClick={() => openPlan(plan.customer_id, date)}>
                Preview
              </Button>
              <Button disabled={busy || !date} onClick={saveAnniversary}>
                Save
              </Button>
            </div>
            {plan.anniversary_date && (
              <button type="button" className="mt-2 text-xs text-status-error hover:underline" disabled={busy} onClick={removeAnniversary}>
                Remove this customer&apos;s anniversary
              </button>
            )}

            {plan.policies.length > 0 && (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-ink-soft">
                    <tr>
                      <th className="py-2 pr-3 font-medium">Cover</th>
                      <th className="py-2 pr-3 font-medium">Expires</th>
                      <th className="py-2 pr-3 text-right font-medium">Current premium</th>
                      <th className="py-2 pr-3 font-medium">Next renewal</th>
                      <th className="py-2 pr-3 text-right font-medium">Estimated premium</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plan.policies.map((p) => (
                      <tr key={p.policy_id} className="border-t border-neutral-border/60 align-top">
                        <td className="py-2.5 pr-3">
                          <span className="font-mono text-xs font-semibold">{p.policy_number}</span>
                          <div className="text-xs text-ink-soft">{p.provider_name}</div>
                        </td>
                        <td className="py-2.5 pr-3 text-xs">{day(p.end_date)}</td>
                        <td className="py-2.5 pr-3 text-right">{kes(p.annual_premium)}</td>
                        <td className="py-2.5 pr-3 text-xs">
                          <Badge tone={p.strategy === "already_aligned" ? "success" : p.very_short ? "error" : "brand"}>{STRATEGY_LABEL[p.strategy]}</Badge>
                          <div className="mt-1">
                            {p.term_days} days, to {day(p.new_end)}
                          </div>
                          <div className="mt-0.5 max-w-xs text-ink-soft">{p.note}</div>
                        </td>
                        <td className="py-2.5 pr-3 text-right">
                          <span className="font-semibold">{kes(p.estimated_premium)}</span>
                          <div className="text-[11px] text-ink-soft">{Number(p.percent_of_annual)}% of annual</div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </Card>

      {list.length > 0 && (
        <Card className="mt-6">
          <h2 className="text-sm font-semibold">Customers with a common anniversary</h2>
          <ul className="mt-2 divide-y divide-neutral-border/60 text-sm">
            {list.map((a) => (
              <li key={a.customer_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>
                  <span className="font-medium text-ink">{a.customer_name}</span>
                  <span className="ml-2 text-xs text-ink-soft">
                    {day(a.anniversary_date)} · {a.active_policies} active {a.active_policies === 1 ? "cover" : "covers"}
                  </span>
                </span>
                <button type="button" className="text-xs font-semibold text-brand-deep hover:underline" onClick={() => openPlan(a.customer_id)}>
                  Open
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* ---- rules (finance / management only) ---- */}
      {!canConfigure && (
        <Card className="mt-6 text-sm text-ink-soft">The rules behind these estimates are set by management and finance roles.</Card>
      )}

      {canConfigure && settings && (
        <>
          <Card className="mt-6">
            <h2 className="text-sm font-semibold">Rules</h2>
            <label className="mt-3 flex items-start gap-3 text-sm">
              <input type="checkbox" className="mt-1 h-4 w-4" checked={settings.enabled} disabled={busy} onChange={(e) => saveSettings({ enabled: e.target.checked })} />
              <span>
                <span className="font-medium text-ink">Show aligned renewals on the renewals screen</span>
                <span className="mt-0.5 block text-xs text-ink-soft">Turning this off hides the alignment from renewals; nothing saved is lost.</span>
              </span>
            </label>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <label className="text-xs text-ink-soft sm:col-span-3">
                How a short period is priced
                <select className={`${INPUT} mt-1 max-w-sm`} value={settings.method} disabled={busy} onChange={(e) => saveSettings({ method: e.target.value as AnniversarySettings["method"] })}>
                  {Object.entries(METHOD_LABEL).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
                <span className="mt-1 block">
                  Pro-rata charges the annual premium by the day. The insurer&apos;s table uses the bands below; a term longer than every band falls back to pro-rata.
                </span>
              </label>
              {(
                [
                  ["year_basis_days", "Days in a year (for pro-rata)", "Usually 365."],
                  ["minimum_premium_pct", "Minimum premium (% of annual)", "A short period never costs less than this."],
                  ["min_stub_days", "Flag very short covers under (days)", "A stub shorter than this is flagged."],
                  ["max_term_days", "Longest cover term allowed (days)", "366 = a year at most. Raise it only if an insurer allows longer."],
                ] as const
              ).map(([key, label, help]) => (
                <label key={key} className="text-xs text-ink-soft">
                  {label}
                  <input
                    className={`${INPUT} mt-1`}
                    type="number"
                    defaultValue={Number(settings[key])}
                    key={`${key}-${settings[key]}`}
                    disabled={busy}
                    onBlur={(e) => e.target.value !== "" && Number(e.target.value) !== Number(settings[key]) && saveSettings({ [key]: e.target.value } as Partial<AnniversarySettings>)}
                  />
                  <span className="mt-1 block">{help}</span>
                </label>
              ))}
            </div>
          </Card>

          <Card className="mt-6">
            <h2 className="text-sm font-semibold">Short-period tables</h2>
            <p className="mt-1 text-xs text-ink-soft">
              Each insurer&apos;s own table: cover for up to N days costs P% of the annual premium. An insurer without a table of its own uses the default table. Only used when
              the method above is the insurer&apos;s table.
            </p>
            <label className="mt-3 block text-xs text-ink-soft">
              Table
              <select className={`${INPUT} mt-1 max-w-xs`} value={table} onChange={(e) => setTable(e.target.value)}>
                <option value="">Default (any insurer)</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            {tableRows.length === 0 ? (
              <p className="mt-3 text-sm text-ink-soft">No bands in this table yet.</p>
            ) : (
              <table className="mt-3 w-full max-w-md text-left text-sm">
                <thead className="text-xs text-ink-soft">
                  <tr>
                    <th className="py-1.5 font-medium">Cover up to (days)</th>
                    <th className="py-1.5 font-medium">% of annual premium</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((b) => (
                    <tr key={b.id} className="border-t border-neutral-border/60">
                      <td className="py-2">{b.up_to_days}</td>
                      <td className="py-2">
                        <input
                          className="w-24 rounded-control border border-neutral-border px-2 py-1 text-sm"
                          type="number"
                          step="0.01"
                          min="0"
                          max="100"
                          defaultValue={Number(b.percent_of_annual)}
                          key={`${b.id}-${b.percent_of_annual}`}
                          disabled={busy}
                          onBlur={(e) =>
                            e.target.value !== "" &&
                            Number(e.target.value) !== Number(b.percent_of_annual) &&
                            run(async () => {
                              await api.patch(`${BASE}/scales/${b.id}`, { percent_of_annual: e.target.value });
                              await loadConfig();
                            })
                          }
                        />
                      </td>
                      <td className="py-2 text-right">
                        <button
                          type="button"
                          className="text-xs text-status-error hover:underline"
                          disabled={busy}
                          onClick={() =>
                            run(async () => {
                              await api.del(`${BASE}/scales/${b.id}`);
                              await loadConfig();
                            })
                          }
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <label className="text-xs text-ink-soft">
                Up to (days)
                <input className={`${INPUT} mt-1 w-32`} type="number" min="1" value={newBand.up_to_days} onChange={(e) => setNewBand({ ...newBand, up_to_days: e.target.value })} />
              </label>
              <label className="text-xs text-ink-soft">
                % of annual
                <input className={`${INPUT} mt-1 w-32`} type="number" min="0" max="100" step="0.01" value={newBand.percent_of_annual} onChange={(e) => setNewBand({ ...newBand, percent_of_annual: e.target.value })} />
              </label>
              <Button onClick={addBand} disabled={busy || !newBand.up_to_days || newBand.percent_of_annual === ""}>
                Add band
              </Button>
            </div>
          </Card>

          <Card className="mt-6">
            <h2 className="text-sm font-semibold">Try the numbers</h2>
            <p className="mt-1 text-xs text-ink-soft">See what the rules above would charge for a cover of a given length.</p>
            <div className="mt-3 grid items-end gap-3 sm:grid-cols-[1fr_1fr_1fr_auto]">
              <label className="text-xs text-ink-soft">
                Annual premium (KES)
                <input className={`${INPUT} mt-1`} type="number" min="1" value={calc.annual} onChange={(e) => setCalc({ ...calc, annual: e.target.value })} />
              </label>
              <label className="text-xs text-ink-soft">
                Cover length (days)
                <input className={`${INPUT} mt-1`} type="number" min="1" value={calc.days} onChange={(e) => setCalc({ ...calc, days: e.target.value })} />
              </label>
              <label className="text-xs text-ink-soft">
                Insurer
                <select className={`${INPUT} mt-1`} value={calc.provider} onChange={(e) => setCalc({ ...calc, provider: e.target.value })}>
                  <option value="">Default table</option>
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <Button variant="ghost" onClick={runCalc} disabled={busy || !calc.annual || !calc.days}>
                Calculate
              </Button>
            </div>
            {calcResult && (
              <p className="mt-3 text-sm text-ink">
                {calcResult.term_days} days → <span className="font-semibold">{kes(calcResult.premium)}</span> ({Number(calcResult.percent_of_annual)}% of annual, {calcResult.method_used.replace(/_/g, " ")})
              </p>
            )}
          </Card>
        </>
      )}
    </main>
  );
}

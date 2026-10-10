"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api, getTokenRole } from "@/lib/api";
import type { AffiliateRateRule, AffiliateSettings } from "@/lib/types";
import { CATEGORIES, CustomerPicker, Field, PickedCustomer, categoryLabel, inputClass, kes } from "@/components/affiliate/shared";

const BASE = "/api/v1/admin/affiliate-program";
const rateText = (type: string, value: string) => (type === "percent" ? `${Number(value)}% of premium` : `${kes(value)} per policy`);

export function RatesTab() {
  const canEdit = ["super_admin", "management"].includes(getTokenRole() ?? "");
  const [settings, setSettings] = useState<AffiliateSettings | null>(null);
  const [rules, setRules] = useState<AffiliateRateRule[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");

  async function load() {
    try {
      const [s, r] = await Promise.all([api.get<AffiliateSettings>(`${BASE}/settings`), api.get<AffiliateRateRule[]>(`${BASE}/rules`)]);
      setSettings(s);
      setRules(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the program settings");
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function saveSettings() {
    if (!settings) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.patch<AffiliateSettings>(
        `${BASE}/settings`,
        {
          program_enabled: settings.program_enabled,
          default_rate_type: settings.default_rate_type,
          default_rate_value: settings.default_rate_value,
          existing_customer_rate_type: settings.existing_customer_rate_value ? settings.existing_customer_rate_type ?? settings.default_rate_type : null,
          existing_customer_rate_value: settings.existing_customer_rate_value ? settings.existing_customer_rate_value : null,
          existing_customer_reward: settings.existing_customer_reward,
          discount_type: settings.discount_type,
          discount_value: settings.discount_value || "0",
          discount_max_amount: settings.discount_max_amount === "" ? null : settings.discount_max_amount,
          discount_valid_days: Number(settings.discount_valid_days),
          min_premium: settings.min_premium === "" ? null : settings.min_premium,
          max_commission_per_policy: settings.max_commission_per_policy === "" ? null : settings.max_commission_per_policy,
          scope: settings.scope,
          window_months: Number(settings.window_months),
          auto_approve: settings.auto_approve,
          allow_self_enrollment: settings.allow_self_enrollment,
        },
        { reason }
      );
      setSettings(updated);
      setReason("");
      setMessage("Settings saved. They apply to every policy issued from now on.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  if (!settings) return <p className="text-ink-soft">{error ?? "Loading…"}</p>;
  const set = <K extends keyof AffiliateSettings>(key: K, value: AffiliateSettings[K]) => setSettings({ ...settings, [key]: value });

  return (
    <div className="flex flex-col gap-8">
      {!canEdit && (
        <p className="rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">Only management can change these. You can view them below.</p>
      )}
      {message && <p className="rounded-control bg-status-success/10 px-4 py-2 text-sm text-status-success">{message}</p>}
      {error && <p className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <Card className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Program settings</h2>
            <p className="text-sm text-ink-soft">Apply to policies issued from now on. Commissions already earned keep the rate they were given.</p>
          </div>
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input type="checkbox" disabled={!canEdit} checked={settings.program_enabled} onChange={(e) => set("program_enabled", e.target.checked)} />
            Program is {settings.program_enabled ? "ON" : "OFF"}
          </label>
        </div>
        {!settings.program_enabled && (
          <p className="rounded-control bg-neutral px-4 py-3 text-sm text-ink-soft">
            While the program is off, nobody earns commission (referrals are still recorded). Set a default rate below, then switch it on.
          </p>
        )}

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Default rate" hint="What a referrer earns when no specific rate below applies to them.">
            <div className="flex gap-2">
              <select disabled={!canEdit} value={settings.default_rate_type} onChange={(e) => set("default_rate_type", e.target.value as "percent" | "fixed")} className={`${inputClass} max-w-[10rem]`}>
                <option value="percent">% of premium</option>
                <option value="fixed">KES per policy</option>
              </select>
              <input type="number" step="0.01" min="0" disabled={!canEdit} value={settings.default_rate_value} onChange={(e) => set("default_rate_value", e.target.value)} className={`${inputClass} max-w-[8rem]`} />
            </div>
          </Field>
          <Field
            label="Rate when the referrer is an existing customer (optional)"
            hint="Used when the person referring already has a policy with us that is currently active (not cancelled or expired). Leave blank to pay them the default rate."
          >
            <div className="flex gap-2">
              <select
                disabled={!canEdit}
                value={settings.existing_customer_rate_type ?? settings.default_rate_type}
                onChange={(e) => set("existing_customer_rate_type", e.target.value as "percent" | "fixed")}
                className={`${inputClass} max-w-[10rem]`}
              >
                <option value="percent">% of premium</option>
                <option value="fixed">KES per policy</option>
              </select>
              <input
                type="number"
                step="0.01"
                min="0"
                disabled={!canEdit}
                placeholder="same as default"
                value={settings.existing_customer_rate_value ?? ""}
                onChange={(e) => set("existing_customer_rate_value", e.target.value === "" ? null : e.target.value)}
                className={`${inputClass} max-w-[9rem]`}
              />
            </div>
          </Field>
          <Field label="Which policies earn commission">
            <select disabled={!canEdit} value={settings.scope} onChange={(e) => set("scope", e.target.value as AffiliateSettings["scope"])} className={inputClass}>
              <option value="first_policy">Only the referred customer&apos;s first policy</option>
              <option value="all_policies">Every policy they buy for a set period</option>
            </select>
            {settings.scope === "all_policies" && (
              <div className="mt-2 flex items-center gap-2 text-sm text-ink-soft">
                for
                <input type="number" min="1" max="120" disabled={!canEdit} value={settings.window_months} onChange={(e) => set("window_months", Number(e.target.value))} className={`${inputClass} max-w-[6rem]`} />
                months after they were referred
              </div>
            )}
          </Field>
          <Field label="Minimum premium (optional)" hint="Policies cheaper than this earn nothing. Leave blank for no minimum.">
            <input type="number" min="0" step="0.01" disabled={!canEdit} value={settings.min_premium ?? ""} onChange={(e) => set("min_premium", e.target.value === "" ? null : e.target.value)} className={inputClass} />
          </Field>
          <Field label="Most one policy can earn (optional)" hint="A ceiling that applies on top of any rate. Leave blank for no cap.">
            <input type="number" min="0" step="0.01" disabled={!canEdit} value={settings.max_commission_per_policy ?? ""} onChange={(e) => set("max_commission_per_policy", e.target.value === "" ? null : e.target.value)} className={inputClass} />
          </Field>
        </div>

        <div className="flex flex-col gap-4 rounded-control bg-neutral/60 p-4">
          <Field
            label="When an existing customer refers someone who buys insurance, reward them with"
            hint="An existing customer is someone with a policy that is currently active. People who aren't customers always earn commission."
          >
            <select
              disabled={!canEdit}
              value={settings.existing_customer_reward}
              onChange={(e) => set("existing_customer_reward", e.target.value as AffiliateSettings["existing_customer_reward"])}
              className={inputClass}
            >
              <option value="commission">Commission (cash)</option>
              <option value="discount">A discount on their own insurance - instead of commission</option>
              <option value="both">Both commission and a discount</option>
            </select>
          </Field>
          {settings.existing_customer_reward !== "commission" && (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Discount" hint="Taken off the premium (before taxes and fees) of the policy staff apply it to.">
                  <div className="flex gap-2">
                    <select disabled={!canEdit} value={settings.discount_type} onChange={(e) => set("discount_type", e.target.value as "percent" | "fixed")} className={`${inputClass} max-w-[9rem]`}>
                      <option value="percent">% off</option>
                      <option value="fixed">KES off</option>
                    </select>
                    <input type="number" min="0" step="0.01" disabled={!canEdit} value={settings.discount_value} onChange={(e) => set("discount_value", e.target.value)} className={`${inputClass} max-w-[7rem]`} />
                  </div>
                </Field>
                <Field label="Most it can take off (optional)">
                  <input type="number" min="0" step="0.01" disabled={!canEdit} value={settings.discount_max_amount ?? ""} onChange={(e) => set("discount_max_amount", e.target.value === "" ? null : e.target.value)} className={inputClass} />
                </Field>
                <Field label="Usable for (days)" hint="After this the credit expires.">
                  <input type="number" min="1" max="3650" disabled={!canEdit} value={settings.discount_valid_days} onChange={(e) => set("discount_valid_days", Number(e.target.value))} className={inputClass} />
                </Field>
              </div>
              <p className="text-xs text-ink-soft">
                A credit does nothing until staff apply it to one of that customer&apos;s applications (Discounts tab), so you decide case by case.
                It can be used on pay-in-full or payment-plan purchases, not on premiums paid through Bidii Credit financing.
              </p>
            </>
          )}
        </div>

        <div className="flex flex-col gap-2 text-sm">
          <label className="flex items-start gap-2">
            <input type="checkbox" className="mt-0.5" disabled={!canEdit} checked={settings.auto_approve} onChange={(e) => set("auto_approve", e.target.checked)} />
            <span><span className="font-medium text-ink">Approve commissions automatically.</span> <span className="text-ink-soft">Leave off to review each one before it can be paid (recommended).</span></span>
          </label>
          <label className="flex items-start gap-2">
            <input type="checkbox" className="mt-0.5" disabled={!canEdit} checked={settings.allow_self_enrollment} onChange={(e) => set("allow_self_enrollment", e.target.checked)} />
            <span><span className="font-medium text-ink">Let customers become affiliates themselves.</span> <span className="text-ink-soft">Otherwise only you can enrol people.</span></span>
          </label>
        </div>

        {canEdit && (
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[16rem] flex-1">
              <Field label="Reason for this change (kept in the audit trail)">
                <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Launch approved by the board" className={inputClass} />
              </Field>
            </div>
            <Button onClick={saveSettings} disabled={busy}>{busy ? "Saving…" : "Save settings"}</Button>
          </div>
        )}
      </Card>

      <RulesSection rules={rules} canEdit={canEdit} onChanged={load} />
      <PreviewSection />
    </div>
  );
}

function RulesSection({ rules, canEdit, onChanged }: { rules: AffiliateRateRule[]; canEdit: boolean; onChanged: () => void }) {
  const empty = { name: "", rate_type: "percent", rate_value: "", max_amount: "", category: "", segment: "", starts_on: "", ends_on: "" };
  const [form, setForm] = useState(empty);
  const [person, setPerson] = useState<PickedCustomer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function add() {
    setBusy(true);
    setError(null);
    try {
      await api.post(
        `${BASE}/rules`,
        {
          name: form.name,
          rate_type: form.rate_type,
          rate_value: form.rate_value,
          max_amount: form.max_amount || null,
          category: form.category || null,
          referrer_segment: form.segment || null,
          affiliate_customer_id: person?.id ?? null,
          starts_on: form.starts_on || null,
          ends_on: form.ends_on || null,
        },
        { reason: `New rate: ${form.name}` }
      );
      setForm(empty);
      setPerson(null);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add the rate");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(rule: AffiliateRateRule) {
    try {
      await api.patch(`${BASE}/rules/${rule.id}`, { active: !rule.active }, { reason: rule.active ? `Switched off: ${rule.name}` : `Switched on: ${rule.name}` });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update the rate");
    }
  }

  async function remove(rule: AffiliateRateRule) {
    if (!window.confirm(`Delete the rate "${rule.name}"? Commissions already earned are not affected.`)) return;
    try {
      await api.del(`${BASE}/rules/${rule.id}`, { reason: `Deleted: ${rule.name}` });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete the rate");
    }
  }

  return (
    <Card className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold">Special rates</h2>
        <p className="text-sm text-ink-soft">
          Give a particular person, a product, a kind of referrer (existing customers or not), or a time-limited promotion its
          own rate. The most specific rate wins: that person + product, then that person, then a product + kind of referrer,
          then a product, then a kind of referrer, then a rate for everyone - and finally the program rates above. If two are
          equally specific, the newest wins.
        </p>
      </div>
      {error && <p className="rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-ink-soft">
            <tr><th className="py-2 pr-3">Name</th><th className="py-2 pr-3">Who</th><th className="py-2 pr-3">Product</th><th className="py-2 pr-3">Rate</th><th className="py-2 pr-3">When</th><th className="py-2"></th></tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id} className="border-t border-neutral-border align-top">
                <td className="py-2 pr-3 font-medium text-ink">{r.name} {!r.active && <Badge tone="neutral">off</Badge>}</td>
                <td className="py-2 pr-3 text-ink-soft">
                  {r.affiliate_name ?? (r.referrer_segment === "existing_customer" ? "Existing customers" : r.referrer_segment === "not_a_customer" ? "Referrers who aren't customers" : "Everyone")}
                  {r.affiliate_name && r.referrer_segment && <p className="text-xs">{r.referrer_segment === "existing_customer" ? "if an existing customer" : "if not a customer"}</p>}
                </td>
                <td className="py-2 pr-3 text-ink-soft">{categoryLabel(r.category)}</td>
                <td className="py-2 pr-3">{rateText(r.rate_type, r.rate_value)}{r.max_amount && <p className="text-xs text-ink-soft">up to {kes(r.max_amount)}</p>}</td>
                <td className="py-2 pr-3 text-xs text-ink-soft">{r.starts_on || r.ends_on ? `${r.starts_on ?? "…"} → ${r.ends_on ?? "…"}` : "Always"}</td>
                <td className="py-2 text-xs font-semibold">
                  {canEdit && (
                    <div className="flex gap-3">
                      <button type="button" onClick={() => toggle(r)} className="text-brand-deep hover:underline">{r.active ? "Turn off" : "Turn on"}</button>
                      <button type="button" onClick={() => remove(r)} className="text-status-error hover:underline">Delete</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {rules.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-ink-soft">No special rates yet - everyone earns the default rate.</td></tr>}
          </tbody>
        </table>
      </div>

      {canEdit && (
        <div className="rounded-control bg-neutral/60 p-4">
          <p className="text-sm font-semibold">Add a special rate</p>
          <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Name"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Kamau Motors partner rate" className={inputClass} /></Field>
            <Field label="For"><CustomerPicker value={person} onChange={setPerson} placeholder="Everyone - or search a person" /></Field>
            <Field label="Product">
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className={inputClass}>
                <option value="">All products</option>
                {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </Field>
            <Field label="Referrer is" hint="An existing customer has a policy with us that is currently active.">
              <select value={form.segment} onChange={(e) => setForm({ ...form, segment: e.target.value })} className={inputClass}>
                <option value="">Anyone</option>
                <option value="existing_customer">An existing customer</option>
                <option value="not_a_customer">Not yet a customer</option>
              </select>
            </Field>
            <Field label="Rate">
              <div className="flex gap-2">
                <select value={form.rate_type} onChange={(e) => setForm({ ...form, rate_type: e.target.value })} className={`${inputClass} max-w-[9rem]`}>
                  <option value="percent">% of premium</option>
                  <option value="fixed">KES per policy</option>
                </select>
                <input type="number" min="0" step="0.01" value={form.rate_value} onChange={(e) => setForm({ ...form, rate_value: e.target.value })} className={`${inputClass} max-w-[7rem]`} />
              </div>
            </Field>
            <Field label="Most per policy (optional)"><input type="number" min="0" step="0.01" value={form.max_amount} onChange={(e) => setForm({ ...form, max_amount: e.target.value })} className={inputClass} /></Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="From (optional)"><input type="date" value={form.starts_on} onChange={(e) => setForm({ ...form, starts_on: e.target.value })} className={inputClass} /></Field>
              <Field label="Until (optional)"><input type="date" value={form.ends_on} onChange={(e) => setForm({ ...form, ends_on: e.target.value })} className={inputClass} /></Field>
            </div>
          </div>
          <div className="mt-4"><Button onClick={add} disabled={busy || !form.name.trim() || form.rate_value === ""}>{busy ? "Adding…" : "Add rate"}</Button></div>
        </div>
      )}
    </Card>
  );
}

function PreviewSection() {
  const [person, setPerson] = useState<PickedCustomer | null>(null);
  const [category, setCategory] = useState("");
  const [premium, setPremium] = useState("20000");
  const [result, setResult] = useState<{ rate_label: string; rate_type: string; rate_value: string; amount: string; below_minimum_premium: boolean; program_enabled: boolean; referrer_is_existing_customer: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function check() {
    if (!person) return;
    setError(null);
    try {
      const params = new URLSearchParams({ referrer_customer_id: person.id, premium });
      if (category) params.set("category", category);
      setResult(await api.get(`${BASE}/preview?${params}`));
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : "Could not check");
    }
  }

  return (
    <Card className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold">Try it</h2>
        <p className="text-sm text-ink-soft">See exactly what someone would earn on a policy, using your current settings. Nothing is recorded.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Referrer"><CustomerPicker value={person} onChange={(c) => { setPerson(c); setResult(null); }} /></Field>
        <Field label="Product">
          <select value={category} onChange={(e) => setCategory(e.target.value)} className={inputClass}>
            <option value="">Any</option>
            {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </Field>
        <Field label="Policy premium (KES)"><input type="number" min="1" value={premium} onChange={(e) => setPremium(e.target.value)} className={inputClass} /></Field>
      </div>
      <div><Button variant="ghost" onClick={check} disabled={!person || !premium}>Check</Button></div>
      {error && <p className="text-sm text-status-error">{error}</p>}
      {result && (
        <div className="rounded-control bg-neutral px-4 py-3 text-sm">
          <p><span className="font-semibold">{person?.full_name}</span> would earn <span className="text-lg font-bold">{kes(result.amount)}</span></p>
          <p className="text-ink-soft">Using “{result.rate_label}” - {rateText(result.rate_type, result.rate_value)}</p>
          <p className="text-ink-soft">{person?.full_name} {result.referrer_is_existing_customer ? "is an existing customer (has an active policy)." : "is not an existing customer (no active policy)."}</p>
          {result.below_minimum_premium && <p className="text-status-error">Below the minimum premium, so nothing would be earned.</p>}
          {!result.program_enabled && <p className="text-status-error">The program is currently OFF, so nothing is being earned yet.</p>}
        </div>
      )}
    </Card>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

interface VehicleClass {
  id: string;
  product_category: string;
  code: string;
  label: string;
  min_sum_insured: string | null;
  max_vehicle_age_years: number | null;
  comprehensive_ineligible_action: string;
  data_confidence: string;
  source_document: string | null;
  notes: string | null;
  is_active: boolean;
}

interface Tier {
  id: string;
  vehicle_class_id: string;
  cover_type: string;
  band_unit: string;
  subtype_key: string | null;
  min_value: string | null;
  max_value: string | null;
  rate_percent: string | null;
  flat_amount: string | null;
  min_premium: string | null;
  label: string | null;
  tier_order: number;
}

interface Extension {
  id: string;
  provider_id: string;
  vehicle_class_id: string | null;
  code: string;
  label: string;
  basis: string;
  rate_percent: string | null;
  flat_amount: string | null;
  min_amount: string | null;
  notes: string | null;
  limit_amount: string | null;
  limit_label: string | null;
}

interface FreeBenefit {
  id: string;
  provider_id: string;
  vehicle_class_id: string | null;
  code: string;
  label: string;
  limit_amount: string | null;
  limit_label: string | null;
  top_up_note: string | null;
  cover_type: string;
  is_active: boolean;
}

interface ClassDetail extends VehicleClass {
  tiers: Tier[];
  extensions: Extension[];
  excesses: unknown[];
  free_benefits: FreeBenefit[];
}

interface PaymentPlan {
  code: string;
  label: string;
  type: "full" | "installments";
  enabled: boolean;
  applies_to: string[];
  deposit_percent: string | null;
  installment_options: number[];
  sticker_months_per_payment: number | null;
}

const emptyTierDraft = {
  cover_type: "comprehensive",
  band_unit: "sum_insured",
  min_value: "",
  max_value: "",
  rate_percent: "",
  flat_amount: "",
  min_premium: "",
  label: "",
};

const emptyFreeBenefitDraft = { code: "", label: "", limit_amount: "", limit_label: "", top_up_note: "", cover_type: "comprehensive" };
const emptyExtensionDraft = {
  code: "",
  label: "",
  basis: "flat",
  rate_percent: "",
  flat_amount: "",
  min_amount: "",
  limit_amount: "",
  limit_label: "",
};
const emptyPlanDraft = {
  code: "",
  label: "",
  type: "installments" as "full" | "installments",
  deposit_percent: "0",
  installment_options: "",
  sticker_months_per_payment: "",
};

export default function RateCardProviderDetailPage({ params }: { params: { providerId: string } }) {
  const { providerId } = params;
  const [classes, setClasses] = useState<VehicleClass[]>([]);
  const [expanded, setExpanded] = useState<Record<string, ClassDetail>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newClass, setNewClass] = useState({
    code: "",
    label: "",
    min_sum_insured: "",
    max_vehicle_age_years: "",
    comprehensive_ineligible_action: "downgrade_to_tpo",
  });
  const [tierDrafts, setTierDrafts] = useState<Record<string, typeof emptyTierDraft>>({});
  const [freeBenefitDrafts, setFreeBenefitDrafts] = useState<Record<string, typeof emptyFreeBenefitDraft>>({});
  const [extensionDrafts, setExtensionDrafts] = useState<Record<string, typeof emptyExtensionDraft>>({});

  const [previewAnswers, setPreviewAnswers] = useState('{\n  "value": 800000,\n  "year": 2020,\n  "usage": "private",\n  "cover_type": "comprehensive"\n}');
  const [previewResult, setPreviewResult] = useState<Record<string, unknown> | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const [plans, setPlans] = useState<PaymentPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [planDraft, setPlanDraft] = useState(emptyPlanDraft);

  async function load() {
    setLoading(true);
    const data = await api.get<VehicleClass[]>(`/api/v1/admin/rate-cards/providers/${providerId}/classes`);
    setClasses(data);
    setLoading(false);
  }

  async function loadPlans() {
    setPlansLoading(true);
    const data = await api.get<PaymentPlan[]>(`/api/v1/admin/rate-cards/providers/${providerId}/payment-plans`);
    setPlans(data);
    setPlansLoading(false);
  }

  useEffect(() => {
    load();
    loadPlans();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerId]);

  async function toggleExpand(classId: string) {
    if (expanded[classId]) {
      const next = { ...expanded };
      delete next[classId];
      setExpanded(next);
      return;
    }
    const detail = await api.get<ClassDetail>(`/api/v1/admin/rate-cards/classes/${classId}`);
    setExpanded((prev) => ({ ...prev, [classId]: detail }));
  }

  async function refreshClass(classId: string) {
    const detail = await api.get<ClassDetail>(`/api/v1/admin/rate-cards/classes/${classId}`);
    setExpanded((prev) => ({ ...prev, [classId]: detail }));
  }

  async function handleCreateClass() {
    if (!newClass.code.trim() || !newClass.label.trim()) return;
    setError(null);
    try {
      await api.post(`/api/v1/admin/rate-cards/providers/${providerId}/classes`, {
        code: newClass.code.trim(),
        label: newClass.label.trim(),
        min_sum_insured: newClass.min_sum_insured ? Number(newClass.min_sum_insured) : null,
        max_vehicle_age_years: newClass.max_vehicle_age_years ? Number(newClass.max_vehicle_age_years) : null,
        comprehensive_ineligible_action: newClass.comprehensive_ineligible_action,
        tiers: [],
      });
      setNewClass({ code: "", label: "", min_sum_insured: "", max_vehicle_age_years: "", comprehensive_ineligible_action: "downgrade_to_tpo" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create class");
    }
  }

  function tierDraftFor(classId: string) {
    return tierDrafts[classId] ?? emptyTierDraft;
  }

  async function handleAddTier(classId: string) {
    const draft = tierDraftFor(classId);
    setError(null);
    try {
      await api.post(`/api/v1/admin/rate-cards/classes/${classId}/tiers`, {
        cover_type: draft.cover_type,
        band_unit: draft.band_unit,
        min_value: draft.min_value ? Number(draft.min_value) : null,
        max_value: draft.max_value ? Number(draft.max_value) : null,
        rate_percent: draft.rate_percent ? Number(draft.rate_percent) : null,
        flat_amount: draft.flat_amount ? Number(draft.flat_amount) : null,
        min_premium: draft.min_premium ? Number(draft.min_premium) : null,
        label: draft.label || null,
      });
      setTierDrafts((prev) => ({ ...prev, [classId]: emptyTierDraft }));
      await refreshClass(classId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add tier");
    }
  }

  async function handleDeleteTier(classId: string, tierId: string) {
    await api.del(`/api/v1/admin/rate-cards/tiers/${tierId}`);
    await refreshClass(classId);
  }

  function freeBenefitDraftFor(classId: string) {
    return freeBenefitDrafts[classId] ?? emptyFreeBenefitDraft;
  }

  async function handleAddFreeBenefit(classId: string) {
    const draft = freeBenefitDraftFor(classId);
    if (!draft.code.trim() || !draft.label.trim()) return;
    setError(null);
    try {
      await api.post(`/api/v1/admin/rate-cards/providers/${providerId}/free-benefits`, {
        vehicle_class_id: classId,
        code: draft.code.trim(),
        label: draft.label.trim(),
        limit_amount: draft.limit_amount ? Number(draft.limit_amount) : null,
        limit_label: draft.limit_label || null,
        top_up_note: draft.top_up_note || null,
        cover_type: draft.cover_type,
      });
      setFreeBenefitDrafts((prev) => ({ ...prev, [classId]: emptyFreeBenefitDraft }));
      await refreshClass(classId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add free benefit");
    }
  }

  async function handleDeleteFreeBenefit(classId: string, benefitId: string) {
    await api.del(`/api/v1/admin/rate-cards/free-benefits/${benefitId}`);
    await refreshClass(classId);
  }

  function extensionDraftFor(classId: string) {
    return extensionDrafts[classId] ?? emptyExtensionDraft;
  }

  async function handleAddExtension(classId: string) {
    const draft = extensionDraftFor(classId);
    if (!draft.code.trim() || !draft.label.trim()) return;
    setError(null);
    try {
      await api.post(`/api/v1/admin/rate-cards/providers/${providerId}/extensions`, {
        vehicle_class_id: classId,
        code: draft.code.trim(),
        label: draft.label.trim(),
        basis: draft.basis,
        rate_percent: draft.rate_percent ? Number(draft.rate_percent) : null,
        flat_amount: draft.flat_amount ? Number(draft.flat_amount) : null,
        min_amount: draft.min_amount ? Number(draft.min_amount) : null,
        limit_amount: draft.limit_amount ? Number(draft.limit_amount) : null,
        limit_label: draft.limit_label || null,
      });
      setExtensionDrafts((prev) => ({ ...prev, [classId]: emptyExtensionDraft }));
      await refreshClass(classId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add extra benefit");
    }
  }

  async function handleDeleteExtension(classId: string, extensionId: string) {
    await api.del(`/api/v1/admin/rate-cards/extensions/${extensionId}`);
    await refreshClass(classId);
  }

  async function handleSavePlans(nextPlans: PaymentPlan[]) {
    setError(null);
    try {
      await api.put(`/api/v1/admin/rate-cards/providers/${providerId}/payment-plans`, { plans: nextPlans });
      setPlans(nextPlans);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save payment plans");
    }
  }

  async function handleApplyTemplate() {
    setError(null);
    try {
      const result = await api.post<PaymentPlan[]>(`/api/v1/admin/rate-cards/providers/${providerId}/payment-plans/apply-template`, {});
      setPlans(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not apply the starter template");
    }
  }

  async function handleAddPlan() {
    if (!planDraft.code.trim() || !planDraft.label.trim()) return;
    const plan: PaymentPlan = {
      code: planDraft.code.trim(),
      label: planDraft.label.trim(),
      type: planDraft.type,
      enabled: true,
      applies_to: ["comprehensive", "tpo"],
      deposit_percent: planDraft.type === "installments" ? planDraft.deposit_percent || "0" : null,
      installment_options:
        planDraft.type === "installments"
          ? planDraft.installment_options
              .split(",")
              .map((s) => parseInt(s.trim(), 10))
              .filter((n) => !Number.isNaN(n) && n > 0)
          : [],
      sticker_months_per_payment: planDraft.sticker_months_per_payment ? Number(planDraft.sticker_months_per_payment) : null,
    };
    await handleSavePlans([...plans, plan]);
    setPlanDraft(emptyPlanDraft);
  }

  async function handleDeletePlan(code: string) {
    await handleSavePlans(plans.filter((p) => p.code !== code));
  }

  async function handleTogglePlan(code: string) {
    await handleSavePlans(plans.map((p) => (p.code === code ? { ...p, enabled: !p.enabled } : p)));
  }

  async function handlePreview() {
    setPreviewError(null);
    setPreviewResult(null);
    try {
      const answers = JSON.parse(previewAnswers);
      const result = await api.post<Record<string, unknown>>(`/api/v1/admin/rate-cards/providers/${providerId}/preview`, {
        answers,
      });
      setPreviewResult(result);
    } catch (e) {
      setPreviewError(e instanceof Error ? e.message : "Preview failed - check the JSON is valid");
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-2xl font-bold">Broker motor terms</h1>
      <p className="mt-1 text-ink-soft">
        Everything a customer&apos;s quote for this broker is computed from: vehicle classes and their rates,
        comprehensive eligibility, free and extra benefits, and how a customer can pay. All fields below are
        optional - leave anything blank to keep this broker priced exactly as it already is.
      </p>

      {error && <div className="mt-4 rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}

      <Card className="mt-6">
        <h2 className="font-semibold">Live preview</h2>
        <p className="mt-1 text-xs text-ink-soft">
          Paste quote-form-shaped answers to sanity-check pricing, eligibility and payment plans immediately after
          an edit. Include &quot;year&quot; to test the vehicle-age eligibility rule.
        </p>
        <textarea
          className="mt-3 w-full rounded-control border border-neutral-border bg-white p-3 font-mono text-xs"
          rows={6}
          value={previewAnswers}
          onChange={(e) => setPreviewAnswers(e.target.value)}
        />
        <Button className="mt-3" variant="ghost" onClick={handlePreview}>
          Run preview
        </Button>
        {previewError && <p className="mt-2 text-sm text-status-error">{previewError}</p>}
        {previewResult && (
          <pre className="mt-3 overflow-x-auto rounded-control bg-neutral p-3 text-xs">{JSON.stringify(previewResult, null, 2)}</pre>
        )}
      </Card>

      {/* ---- Payment plans (broker-level) -------------------------------- */}
      <Card className="mt-6">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">How customers can pay</h2>
          {!plansLoading && plans.length === 0 && (
            <Button variant="ghost" onClick={handleApplyTemplate}>
              Start from a typical template
            </Button>
          )}
        </div>
        <p className="mt-1 text-xs text-ink-soft">
          Pay in full is always available. Add a plan below to also offer a deposit + monthly instalments (e.g. 30%
          then 3 or 4 months), or a straight monthly plan - set &quot;sticker months per payment&quot; to 1 if each
          monthly payment should issue one month of sticker cover.
        </p>

        {!plansLoading && plans.length > 0 && (
          <table className="mt-4 w-full text-left text-sm">
            <thead className="text-xs uppercase text-ink-soft">
              <tr>
                <th className="pb-2">Plan</th>
                <th className="pb-2">Type</th>
                <th className="pb-2">Deposit</th>
                <th className="pb-2">Instalments</th>
                <th className="pb-2">Sticker/payment</th>
                <th className="pb-2">Active</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody>
              {plans.map((p) => (
                <tr key={p.code} className="border-t border-neutral-border">
                  <td className="py-1.5">
                    {p.label} <span className="text-xs text-ink-soft">({p.code})</span>
                  </td>
                  <td className="py-1.5">{p.type}</td>
                  <td className="py-1.5">{p.deposit_percent ? `${p.deposit_percent}%` : "—"}</td>
                  <td className="py-1.5">{p.installment_options.join(", ") || "—"}</td>
                  <td className="py-1.5">{p.sticker_months_per_payment ?? "—"}</td>
                  <td className="py-1.5">
                    <button className="text-xs text-status-info" onClick={() => handleTogglePlan(p.code)}>
                      {p.enabled ? "Enabled" : "Disabled"}
                    </button>
                  </td>
                  <td className="py-1.5">
                    <button className="text-xs text-status-error" onClick={() => handleDeletePlan(p.code)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <input
            className="rounded-control border border-neutral-border px-3 py-2 text-sm"
            placeholder="Code (e.g. deposit_30)"
            value={planDraft.code}
            onChange={(e) => setPlanDraft({ ...planDraft, code: e.target.value })}
          />
          <input
            className="rounded-control border border-neutral-border px-3 py-2 text-sm"
            placeholder="Label shown to customers"
            value={planDraft.label}
            onChange={(e) => setPlanDraft({ ...planDraft, label: e.target.value })}
          />
          <select
            className="rounded-control border border-neutral-border px-3 py-2 text-sm"
            value={planDraft.type}
            onChange={(e) => setPlanDraft({ ...planDraft, type: e.target.value as "full" | "installments" })}
          >
            <option value="installments">Deposit + instalments / monthly</option>
            <option value="full">Pay in full</option>
          </select>
          {planDraft.type === "installments" && (
            <>
              <input
                className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                placeholder="Deposit % (0 for none, e.g. monthly)"
                value={planDraft.deposit_percent}
                onChange={(e) => setPlanDraft({ ...planDraft, deposit_percent: e.target.value })}
              />
              <input
                className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                placeholder="Instalment counts, comma-separated (e.g. 3,4)"
                value={planDraft.installment_options}
                onChange={(e) => setPlanDraft({ ...planDraft, installment_options: e.target.value })}
              />
              <input
                className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                placeholder="Sticker months per payment (optional)"
                value={planDraft.sticker_months_per_payment}
                onChange={(e) => setPlanDraft({ ...planDraft, sticker_months_per_payment: e.target.value })}
              />
            </>
          )}
        </div>
        <Button variant="ghost" className="mt-2" onClick={handleAddPlan}>
          Add plan
        </Button>
      </Card>

      {/* ---- New vehicle class ------------------------------------------- */}
      <Card className="mt-6 grid gap-3 sm:grid-cols-3">
        <Input label="Class code" placeholder="motor_private" value={newClass.code} onChange={(e) => setNewClass({ ...newClass, code: e.target.value })} />
        <Input label="Label" placeholder="Motor Private (070)" value={newClass.label} onChange={(e) => setNewClass({ ...newClass, label: e.target.value })} />
        <Input
          label="Min sum insured for comprehensive (optional)"
          type="number"
          placeholder="500000"
          value={newClass.min_sum_insured}
          onChange={(e) => setNewClass({ ...newClass, min_sum_insured: e.target.value })}
        />
        <Input
          label="Max vehicle age for comprehensive, years (optional)"
          type="number"
          placeholder="15"
          value={newClass.max_vehicle_age_years}
          onChange={(e) => setNewClass({ ...newClass, max_vehicle_age_years: e.target.value })}
        />
        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <label className="text-sm font-medium text-ink">If a vehicle falls outside those limits</label>
          <select
            className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm"
            value={newClass.comprehensive_ineligible_action}
            onChange={(e) => setNewClass({ ...newClass, comprehensive_ineligible_action: e.target.value })}
          >
            <option value="downgrade_to_tpo">Quote Third Party Only instead</option>
            <option value="decline">Don&apos;t offer a quote from this broker</option>
          </select>
        </div>
        <Button onClick={handleCreateClass} className="sm:col-span-3">
          Add vehicle class
        </Button>
      </Card>

      <div className="mt-6 flex flex-col gap-3">
        {loading && <p className="text-ink-soft">Loading…</p>}
        {!loading &&
          classes.map((c) => (
            <Card key={c.id}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{c.label}</h3>
                    <Badge tone="neutral">{c.code}</Badge>
                    <Badge tone={c.data_confidence === "verified" ? "success" : "error"}>{c.data_confidence}</Badge>
                  </div>
                  {c.source_document && <p className="mt-1 text-xs text-ink-soft">{c.source_document}</p>}
                  {(c.min_sum_insured || c.max_vehicle_age_years) && (
                    <p className="mt-1 text-xs text-ink-soft">
                      Comprehensive needs{c.min_sum_insured ? ` ≥ KES ${Number(c.min_sum_insured).toLocaleString()}` : ""}
                      {c.min_sum_insured && c.max_vehicle_age_years ? " and" : ""}
                      {c.max_vehicle_age_years ? ` ≤ ${c.max_vehicle_age_years} years old` : ""} - otherwise{" "}
                      {c.comprehensive_ineligible_action === "decline" ? "no quote from this broker" : "priced as TPO"}.
                    </p>
                  )}
                </div>
                <Button variant="ghost" onClick={() => toggleExpand(c.id)}>
                  {expanded[c.id] ? "Hide details" : "Show details"}
                </Button>
              </div>

              {expanded[c.id] && (
                <div className="mt-4 flex flex-col gap-6 border-t border-neutral-border pt-4">
                  {/* Tiers */}
                  <div>
                    <h4 className="text-sm font-semibold text-ink">Rate tiers</h4>
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full min-w-[720px] text-left text-sm">
                        <thead className="text-xs uppercase text-ink-soft">
                          <tr>
                            <th className="pb-2">Cover</th>
                            <th className="pb-2">Band</th>
                            <th className="pb-2">Range</th>
                            <th className="pb-2">Rate %</th>
                            <th className="pb-2">Flat</th>
                            <th className="pb-2">Min premium</th>
                            <th className="pb-2">Label</th>
                            <th className="pb-2" />
                          </tr>
                        </thead>
                        <tbody>
                          {expanded[c.id].tiers.map((t) => (
                            <tr key={t.id} className="border-t border-neutral-border">
                              <td className="py-1.5">{t.cover_type}</td>
                              <td className="py-1.5">{t.band_unit}</td>
                              <td className="py-1.5">
                                {t.min_value ?? "—"} - {t.max_value ?? "∞"}
                              </td>
                              <td className="py-1.5">{t.rate_percent ?? "—"}</td>
                              <td className="py-1.5">{t.flat_amount ?? "—"}</td>
                              <td className="py-1.5">{t.min_premium ?? "—"}</td>
                              <td className="py-1.5">{t.label ?? "—"}</td>
                              <td className="py-1.5">
                                <button className="text-xs text-status-error" onClick={() => handleDeleteTier(c.id, t.id)}>
                                  Delete
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    <div className="mt-4 grid gap-2 sm:grid-cols-4">
                      <select
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        value={tierDraftFor(c.id).cover_type}
                        onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), cover_type: e.target.value } }))}
                      >
                        <option value="comprehensive">Comprehensive</option>
                        <option value="tpo">TPO</option>
                      </select>
                      <select
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        value={tierDraftFor(c.id).band_unit}
                        onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), band_unit: e.target.value } }))}
                      >
                        <option value="sum_insured">Sum insured</option>
                        <option value="tonnes">Tonnes</option>
                        <option value="passengers">Passengers</option>
                        <option value="subtype">Subtype</option>
                        <option value="none">None (flat)</option>
                      </select>
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Min"
                        value={tierDraftFor(c.id).min_value}
                        onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), min_value: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Max (blank = unbounded)"
                        value={tierDraftFor(c.id).max_value}
                        onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), max_value: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Rate %"
                        value={tierDraftFor(c.id).rate_percent}
                        onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), rate_percent: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Flat amount"
                        value={tierDraftFor(c.id).flat_amount}
                        onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), flat_amount: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Min premium"
                        value={tierDraftFor(c.id).min_premium}
                        onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), min_premium: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Label"
                        value={tierDraftFor(c.id).label}
                        onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), label: e.target.value } }))}
                      />
                    </div>
                    <Button variant="ghost" className="mt-2" onClick={() => handleAddTier(c.id)}>
                      Add tier
                    </Button>
                  </div>

                  {/* Free benefits */}
                  <div>
                    <h4 className="text-sm font-semibold text-ink">Free (included) benefits</h4>
                    <p className="mt-1 text-xs text-ink-soft">
                      Shown to the customer at quote time, never priced - windscreen, third party property damage,
                      towing, and so on.
                    </p>
                    {expanded[c.id].free_benefits.length > 0 && (
                      <table className="mt-2 w-full text-left text-sm">
                        <thead className="text-xs uppercase text-ink-soft">
                          <tr>
                            <th className="pb-2">Benefit</th>
                            <th className="pb-2">Limit</th>
                            <th className="pb-2">Top-up note</th>
                            <th className="pb-2">Cover</th>
                            <th className="pb-2" />
                          </tr>
                        </thead>
                        <tbody>
                          {expanded[c.id].free_benefits.map((b) => (
                            <tr key={b.id} className="border-t border-neutral-border">
                              <td className="py-1.5">{b.label}</td>
                              <td className="py-1.5">{b.limit_label ?? (b.limit_amount ? `Up to ${b.limit_amount}` : "—")}</td>
                              <td className="py-1.5">{b.top_up_note ?? "—"}</td>
                              <td className="py-1.5">{b.cover_type}</td>
                              <td className="py-1.5">
                                <button className="text-xs text-status-error" onClick={() => handleDeleteFreeBenefit(c.id, b.id)}>
                                  Delete
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Code (e.g. windscreen)"
                        value={freeBenefitDraftFor(c.id).code}
                        onChange={(e) => setFreeBenefitDrafts((prev) => ({ ...prev, [c.id]: { ...freeBenefitDraftFor(c.id), code: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Label"
                        value={freeBenefitDraftFor(c.id).label}
                        onChange={(e) => setFreeBenefitDrafts((prev) => ({ ...prev, [c.id]: { ...freeBenefitDraftFor(c.id), label: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Limit label (e.g. Up to KES 30,000)"
                        value={freeBenefitDraftFor(c.id).limit_label}
                        onChange={(e) => setFreeBenefitDrafts((prev) => ({ ...prev, [c.id]: { ...freeBenefitDraftFor(c.id), limit_label: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Top-up note (optional)"
                        value={freeBenefitDraftFor(c.id).top_up_note}
                        onChange={(e) => setFreeBenefitDrafts((prev) => ({ ...prev, [c.id]: { ...freeBenefitDraftFor(c.id), top_up_note: e.target.value } }))}
                      />
                      <select
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        value={freeBenefitDraftFor(c.id).cover_type}
                        onChange={(e) => setFreeBenefitDrafts((prev) => ({ ...prev, [c.id]: { ...freeBenefitDraftFor(c.id), cover_type: e.target.value } }))}
                      >
                        <option value="comprehensive">Comprehensive</option>
                        <option value="tpo">TPO</option>
                      </select>
                    </div>
                    <Button variant="ghost" className="mt-2" onClick={() => handleAddFreeBenefit(c.id)}>
                      Add free benefit
                    </Button>
                  </div>

                  {/* Extra (priced, optional) benefits */}
                  <div>
                    <h4 className="text-sm font-semibold text-ink">Extra benefits (optional, priced)</h4>
                    <p className="mt-1 text-xs text-ink-soft">
                      Courtesy car, loss of keys, political violence, excess protector, and so on - only what this
                      broker actually offers needs a row here.
                    </p>
                    {expanded[c.id].extensions.length > 0 && (
                      <table className="mt-2 w-full text-left text-sm">
                        <thead className="text-xs uppercase text-ink-soft">
                          <tr>
                            <th className="pb-2">Benefit</th>
                            <th className="pb-2">Basis</th>
                            <th className="pb-2">Rate/Amount</th>
                            <th className="pb-2">Limit</th>
                            <th className="pb-2" />
                          </tr>
                        </thead>
                        <tbody>
                          {expanded[c.id].extensions.map((ext) => (
                            <tr key={ext.id} className="border-t border-neutral-border">
                              <td className="py-1.5">{ext.label}</td>
                              <td className="py-1.5">{ext.basis}</td>
                              <td className="py-1.5">{ext.rate_percent ? `${ext.rate_percent}%` : ext.flat_amount ?? "—"}</td>
                              <td className="py-1.5">{ext.limit_label ?? (ext.limit_amount ? `Up to ${ext.limit_amount}` : "—")}</td>
                              <td className="py-1.5">
                                <button className="text-xs text-status-error" onClick={() => handleDeleteExtension(c.id, ext.id)}>
                                  Delete
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    <div className="mt-3 grid gap-2 sm:grid-cols-4">
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Code (e.g. courtesy_car)"
                        value={extensionDraftFor(c.id).code}
                        onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), code: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Label"
                        value={extensionDraftFor(c.id).label}
                        onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), label: e.target.value } }))}
                      />
                      <select
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        value={extensionDraftFor(c.id).basis}
                        onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), basis: e.target.value } }))}
                      >
                        <option value="flat">Flat amount</option>
                        <option value="percent_of_sum_insured">% of sum insured</option>
                        <option value="per_person">Per person (seating capacity)</option>
                      </select>
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Rate % (if % basis)"
                        value={extensionDraftFor(c.id).rate_percent}
                        onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), rate_percent: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Flat amount (if flat/per-person basis)"
                        value={extensionDraftFor(c.id).flat_amount}
                        onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), flat_amount: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Minimum amount (if % basis)"
                        value={extensionDraftFor(c.id).min_amount}
                        onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), min_amount: e.target.value } }))}
                      />
                      <input
                        className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                        placeholder="Limit label (e.g. Up to KES 30,000)"
                        value={extensionDraftFor(c.id).limit_label}
                        onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), limit_label: e.target.value } }))}
                      />
                    </div>
                    <Button variant="ghost" className="mt-2" onClick={() => handleAddExtension(c.id)}>
                      Add extra benefit
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          ))}
      </div>
    </main>
  );
}

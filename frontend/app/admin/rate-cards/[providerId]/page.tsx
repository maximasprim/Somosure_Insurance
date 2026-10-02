"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
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

interface Excess {
  id: string;
  provider_id: string;
  vehicle_class_id: string;
  peril: string;
  basis: string;
  rate_percent: string | null;
  flat_amount: string | null;
  min_amount: string | null;
  label: string | null;
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
  excesses: Excess[];
  extensions: Extension[];
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

type ClassTab = "tiers" | "excesses" | "free_benefits" | "extensions";

const TAB_LABELS: Record<ClassTab, string> = {
  tiers: "Rate tiers",
  excesses: "Excesses",
  free_benefits: "Free benefits",
  extensions: "Extra benefits",
};

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

const emptyExcessDraft = { peril: "", basis: "percent_of_sum_insured", rate_percent: "", flat_amount: "", min_amount: "", label: "" };
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

// A small labelled field wrapper so every input in this page reads the
// same way: what the field is for, then the control itself. Plain inputs
// below use this instead of relying on placeholder text, which disappears
// the moment someone starts typing.
function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-ink-soft">{label}</label>
      {children}
      {hint && <p className="text-[11px] text-neutral-500">{hint}</p>}
    </div>
  );
}

const inputClass = "rounded-control border border-neutral-border px-3 py-2 text-sm";

export default function RateCardProviderDetailPage({ params }: { params: { providerId: string } }) {
  const { providerId } = params;
  const [classes, setClasses] = useState<VehicleClass[]>([]);
  const [expanded, setExpanded] = useState<Record<string, ClassDetail>>({});
  const [activeTab, setActiveTab] = useState<Record<string, ClassTab>>({});
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
  const [excessDrafts, setExcessDrafts] = useState<Record<string, typeof emptyExcessDraft>>({});
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
    setActiveTab((prev) => ({ ...prev, [classId]: prev[classId] ?? "tiers" }));
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

  function excessDraftFor(classId: string) {
    return excessDrafts[classId] ?? emptyExcessDraft;
  }

  async function handleAddExcess(classId: string) {
    const draft = excessDraftFor(classId);
    if (!draft.peril.trim()) return;
    setError(null);
    try {
      await api.post(`/api/v1/admin/rate-cards/classes/${classId}/excesses`, {
        vehicle_class_id: classId,
        peril: draft.peril.trim(),
        basis: draft.basis,
        rate_percent: draft.rate_percent ? Number(draft.rate_percent) : null,
        flat_amount: draft.flat_amount ? Number(draft.flat_amount) : null,
        min_amount: draft.min_amount ? Number(draft.min_amount) : null,
        label: draft.label || null,
      });
      setExcessDrafts((prev) => ({ ...prev, [classId]: emptyExcessDraft }));
      await refreshClass(classId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add excess");
    }
  }

  async function handleDeleteExcess(classId: string, excessId: string) {
    await api.del(`/api/v1/admin/rate-cards/excesses/${excessId}`);
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
    <main className="mx-auto max-w-8xl px-3 py-4">
      <h1 className="text-2xl font-bold">Broker motor terms</h1>
      <p className="mt-1 text-ink-soft">
        Everything a customer&apos;s quote for this broker is computed from, in the order it&apos;s used:
      </p>
      <ol className="mt-2 flex flex-col gap-1 text-sm text-ink-soft">
        <li>
          <strong className="text-ink">1. Vehicle classes</strong> - e.g. &quot;Motor Private&quot; - each with its own rate
          tiers (how the premium is calculated) and excesses (what the customer pays towards a claim).
        </li>
        <li>
          <strong className="text-ink">2. Free &amp; extra benefits</strong> - what&apos;s already included in the price,
          and what costs more.
        </li>
        <li>
          <strong className="text-ink">3. Payment plans</strong> - how a customer is allowed to pay once they&apos;ve
          chosen a quote.
        </li>
      </ol>
      <p className="mt-2 text-sm text-ink-soft">
        Every field below is optional - leave anything blank to keep this broker priced exactly as it already is.
      </p>

      {error && <div className="mt-4 rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}

      <Card className="mt-6">
        <h2 className="font-semibold">Test your changes</h2>
        <p className="mt-1 text-xs text-ink-soft">
          Paste quote-form-shaped answers below and run a preview any time after an edit, to see the exact premium,
          eligibility outcome and payment plans a real customer would get - without creating a real quote. Include
          &quot;year&quot; to test the vehicle-age eligibility rule.
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
          <h2 className="font-semibold">Step 3: How customers can pay</h2>
          {!plansLoading && plans.length === 0 && (
            <Button variant="ghost" onClick={handleApplyTemplate}>
              Start from a typical template
            </Button>
          )}
        </div>
        <p className="mt-1 text-xs text-ink-soft">
          Pay in full is always available even with no plans listed below. Add a plan to also offer a deposit plus
          monthly instalments (e.g. 30% now, then 3 or 4 months), or a straight monthly plan - set &quot;sticker
          months per payment&quot; to 1 if each monthly payment should issue one month of sticker cover.
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

        <p className="mt-4 text-xs font-medium text-ink-soft">Add a plan</p>
        <div className="mt-2 grid gap-2 sm:grid-cols-3">
          <Field label="Internal code" hint="A short id, e.g. deposit_30 - never shown to the customer.">
            <input
              className={inputClass}
              placeholder="deposit_30"
              value={planDraft.code}
              onChange={(e) => setPlanDraft({ ...planDraft, code: e.target.value })}
            />
          </Field>
          <Field label="Label shown to customers">
            <input
              className={inputClass}
              placeholder="30% deposit, pay the rest monthly"
              value={planDraft.label}
              onChange={(e) => setPlanDraft({ ...planDraft, label: e.target.value })}
            />
          </Field>
          <Field label="Plan type">
            <select
              className={inputClass}
              value={planDraft.type}
              onChange={(e) => setPlanDraft({ ...planDraft, type: e.target.value as "full" | "installments" })}
            >
              <option value="installments">Deposit + instalments / monthly</option>
              <option value="full">Pay in full</option>
            </select>
          </Field>
          {planDraft.type === "installments" && (
            <>
              <Field label="Deposit %" hint="Use 0 for a plan with no deposit, e.g. a straight monthly plan.">
                <input
                  className={inputClass}
                  placeholder="30"
                  value={planDraft.deposit_percent}
                  onChange={(e) => setPlanDraft({ ...planDraft, deposit_percent: e.target.value })}
                />
              </Field>
              <Field label="Instalment counts" hint="Comma-separated - the customer picks one, e.g. 3,4 or just 12.">
                <input
                  className={inputClass}
                  placeholder="3,4"
                  value={planDraft.installment_options}
                  onChange={(e) => setPlanDraft({ ...planDraft, installment_options: e.target.value })}
                />
              </Field>
              <Field label="Sticker months per payment" hint="Leave blank unless each payment should renew the sticker.">
                <input
                  className={inputClass}
                  placeholder="e.g. 1"
                  value={planDraft.sticker_months_per_payment}
                  onChange={(e) => setPlanDraft({ ...planDraft, sticker_months_per_payment: e.target.value })}
                />
              </Field>
            </>
          )}
        </div>
        <Button variant="ghost" className="mt-3" onClick={handleAddPlan}>
          Add plan
        </Button>
      </Card>

      {/* ---- New vehicle class ------------------------------------------- */}
      <Card className="mt-6">
        <h2 className="font-semibold">Step 1: Add a vehicle class</h2>
        <p className="mt-1 text-xs text-ink-soft">
          A vehicle class is one category this broker prices separately, e.g. &quot;Motor Private&quot; or &quot;Motor
          Commercial - Own Goods&quot;. After creating one below, expand it in the list to add its rate tiers,
          excesses, and benefits.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Field label="Class code" hint="A short id with no spaces, e.g. motor_private.">
            <input
              className={inputClass}
              placeholder="motor_private"
              value={newClass.code}
              onChange={(e) => setNewClass({ ...newClass, code: e.target.value })}
            />
          </Field>
          <Field label="Label shown to admins">
            <input
              className={inputClass}
              placeholder="Motor Private (070)"
              value={newClass.label}
              onChange={(e) => setNewClass({ ...newClass, label: e.target.value })}
            />
          </Field>
          <div />
          <Field label="Min. sum insured for comprehensive (optional)" hint="Below this value, comprehensive isn't offered.">
            <input
              className={inputClass}
              type="number"
              placeholder="500000"
              value={newClass.min_sum_insured}
              onChange={(e) => setNewClass({ ...newClass, min_sum_insured: e.target.value })}
            />
          </Field>
          <Field label="Max. vehicle age, years (optional)" hint="Above this age, comprehensive isn't offered.">
            <input
              className={inputClass}
              type="number"
              placeholder="15"
              value={newClass.max_vehicle_age_years}
              onChange={(e) => setNewClass({ ...newClass, max_vehicle_age_years: e.target.value })}
            />
          </Field>
          <Field label="If a vehicle falls outside those limits">
            <select
              className={inputClass}
              value={newClass.comprehensive_ineligible_action}
              onChange={(e) => setNewClass({ ...newClass, comprehensive_ineligible_action: e.target.value })}
            >
              <option value="downgrade_to_tpo">Quote Third Party Only instead</option>
              <option value="decline">Don&apos;t offer a quote from this broker</option>
            </select>
          </Field>
        </div>
        <Button onClick={handleCreateClass} className="mt-4">
          Add vehicle class
        </Button>
      </Card>

      {/* ---- Vehicle class list ------------------------------------------- */}
      <h2 className="mt-8 font-semibold">Step 2: Vehicle classes</h2>
      <div className="mt-3 flex flex-col gap-3">
        {loading && <p className="text-ink-soft">Loading…</p>}
        {!loading && classes.length === 0 && (
          <p className="text-sm text-ink-soft">
            No vehicle classes yet - add one above to start pricing motor quotes for this broker.
          </p>
        )}
        {!loading &&
          classes.map((c) => {
            const detail = expanded[c.id];
            const tab = activeTab[c.id] ?? "tiers";
            return (
              <Card key={c.id}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">{c.label}</h3>
                      <Badge tone="neutral">{c.code}</Badge>
                      <Badge tone={c.data_confidence === "verified" ? "success" : "error"}>{c.data_confidence}</Badge>
                    </div>
                    {c.source_document && <p className="mt-1 text-xs text-ink-soft">Source: {c.source_document}</p>}
                    {(c.min_sum_insured || c.max_vehicle_age_years) && (
                      <p className="mt-1 text-xs text-ink-soft">
                        Comprehensive needs{c.min_sum_insured ? ` a value of at least KES ${Number(c.min_sum_insured).toLocaleString()}` : ""}
                        {c.min_sum_insured && c.max_vehicle_age_years ? " and" : ""}
                        {c.max_vehicle_age_years ? ` an age of ${c.max_vehicle_age_years} years or under` : ""} - otherwise{" "}
                        {c.comprehensive_ineligible_action === "decline" ? "this broker won't quote" : "it's priced as Third Party Only"}.
                      </p>
                    )}
                  </div>
                  <Button variant="ghost" onClick={() => toggleExpand(c.id)}>
                    {detail ? "Hide details" : "Show details"}
                  </Button>
                </div>

                {detail && (
                  <div className="mt-4 border-t border-neutral-border pt-4">
                    {/* Tab bar */}
                    <div className="flex flex-wrap gap-1 border-b border-neutral-border pb-2">
                      {(Object.keys(TAB_LABELS) as ClassTab[]).map((key) => {
                        const count =
                          key === "tiers" ? detail.tiers.length
                          : key === "excesses" ? detail.excesses.length
                          : key === "free_benefits" ? detail.free_benefits.length
                          : detail.extensions.length;
                        const isActive = tab === key;
                        return (
                          <button
                            key={key}
                            onClick={() => setActiveTab((prev) => ({ ...prev, [c.id]: key }))}
                            className={`rounded-control px-3 py-1.5 text-sm ${
                              isActive ? "bg-brand-tint font-semibold text-ink" : "text-ink-soft hover:bg-neutral"
                            }`}
                          >
                            {TAB_LABELS[key]} {count > 0 && <span className="text-xs text-ink-soft">({count})</span>}
                          </button>
                        );
                      })}
                    </div>

                    {/* --- Tiers --- */}
                    {tab === "tiers" && (
                      <div className="mt-4">
                        <p className="text-xs text-ink-soft">
                          How the premium is calculated. Each tier applies to one cover type (comprehensive or TPO)
                          and one range of values - a customer's quote uses whichever tier their vehicle falls
                          into.
                        </p>
                        {detail.tiers.length > 0 && (
                          <div className="mt-3 overflow-x-auto">
                            <table className="w-full min-w-[720px] text-left text-sm">
                              <thead className="text-xs uppercase text-ink-soft">
                                <tr>
                                  <th className="pb-2">Cover</th>
                                  <th className="pb-2">Banded by</th>
                                  <th className="pb-2">Range</th>
                                  <th className="pb-2">Rate %</th>
                                  <th className="pb-2">Flat</th>
                                  <th className="pb-2">Min premium</th>
                                  <th className="pb-2">Label</th>
                                  <th className="pb-2" />
                                </tr>
                              </thead>
                              <tbody>
                                {detail.tiers.map((t) => (
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
                        )}

                        <p className="mt-4 text-xs font-medium text-ink-soft">Add a tier</p>
                        <div className="mt-2 grid gap-2 sm:grid-cols-4">
                          <Field label="Cover type">
                            <select
                              className={inputClass}
                              value={tierDraftFor(c.id).cover_type}
                              onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), cover_type: e.target.value } }))}
                            >
                              <option value="comprehensive">Comprehensive</option>
                              <option value="tpo">Third Party Only</option>
                            </select>
                          </Field>
                          <Field label="Banded by" hint="What the min/max range below is measured in.">
                            <select
                              className={inputClass}
                              value={tierDraftFor(c.id).band_unit}
                              onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), band_unit: e.target.value } }))}
                            >
                              <option value="sum_insured">Vehicle value (sum insured)</option>
                              <option value="tonnes">Tonnage</option>
                              <option value="passengers">Passenger count</option>
                              <option value="subtype">Named subtype (e.g. prime mover)</option>
                              <option value="none">None - one flat rate for this cover type</option>
                            </select>
                          </Field>
                          <Field label="Range min" hint="Leave blank for no lower limit.">
                            <input
                              className={inputClass}
                              placeholder="0"
                              value={tierDraftFor(c.id).min_value}
                              onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), min_value: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Range max" hint="Leave blank for no upper limit.">
                            <input
                              className={inputClass}
                              placeholder="unbounded"
                              value={tierDraftFor(c.id).max_value}
                              onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), max_value: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Rate %" hint="Use this OR a flat amount, not both.">
                            <input
                              className={inputClass}
                              placeholder="e.g. 5"
                              value={tierDraftFor(c.id).rate_percent}
                              onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), rate_percent: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Flat amount (KES)">
                            <input
                              className={inputClass}
                              placeholder="e.g. 7500"
                              value={tierDraftFor(c.id).flat_amount}
                              onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), flat_amount: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Minimum premium (KES)" hint="The premium never goes below this.">
                            <input
                              className={inputClass}
                              placeholder="e.g. 37500"
                              value={tierDraftFor(c.id).min_premium}
                              onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), min_premium: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Label (optional)" hint="How this tier is described to admins, e.g. 'Up to 1,000,000'.">
                            <input
                              className={inputClass}
                              placeholder="Up to 1,000,000"
                              value={tierDraftFor(c.id).label}
                              onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), label: e.target.value } }))}
                            />
                          </Field>
                        </div>
                        <Button variant="ghost" className="mt-3" onClick={() => handleAddTier(c.id)}>
                          Add tier
                        </Button>
                      </div>
                    )}

                    {/* --- Excesses --- */}
                    {tab === "excesses" && (
                      <div className="mt-4">
                        <p className="text-xs text-ink-soft">
                          What the customer still pays towards a claim for a given peril (e.g. theft, own damage) -
                          shown to the customer for information, never charged as part of the premium.
                        </p>
                        {detail.excesses.length > 0 && (
                          <table className="mt-3 w-full text-left text-sm">
                            <thead className="text-xs uppercase text-ink-soft">
                              <tr>
                                <th className="pb-2">Peril</th>
                                <th className="pb-2">Basis</th>
                                <th className="pb-2">Rate / Amount</th>
                                <th className="pb-2">Minimum</th>
                                <th className="pb-2">Label</th>
                                <th className="pb-2" />
                              </tr>
                            </thead>
                            <tbody>
                              {detail.excesses.map((ex) => (
                                <tr key={ex.id} className="border-t border-neutral-border">
                                  <td className="py-1.5">{ex.peril}</td>
                                  <td className="py-1.5">{ex.basis}</td>
                                  <td className="py-1.5">{ex.rate_percent ? `${ex.rate_percent}%` : ex.flat_amount ?? "—"}</td>
                                  <td className="py-1.5">{ex.min_amount ?? "—"}</td>
                                  <td className="py-1.5">{ex.label ?? "—"}</td>
                                  <td className="py-1.5">
                                    <button className="text-xs text-status-error" onClick={() => handleDeleteExcess(c.id, ex.id)}>
                                      Delete
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}

                        <p className="mt-4 text-xs font-medium text-ink-soft">Add an excess</p>
                        <div className="mt-2 grid gap-2 sm:grid-cols-3">
                          <Field label="Peril" hint="A short id, e.g. own_damage, theft_with_tracking.">
                            <input
                              className={inputClass}
                              placeholder="own_damage"
                              value={excessDraftFor(c.id).peril}
                              onChange={(e) => setExcessDrafts((prev) => ({ ...prev, [c.id]: { ...excessDraftFor(c.id), peril: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Basis">
                            <select
                              className={inputClass}
                              value={excessDraftFor(c.id).basis}
                              onChange={(e) => setExcessDrafts((prev) => ({ ...prev, [c.id]: { ...excessDraftFor(c.id), basis: e.target.value } }))}
                            >
                              <option value="percent_of_sum_insured">% of sum insured</option>
                              <option value="flat">Flat amount</option>
                            </select>
                          </Field>
                          <Field label="Rate % (if % basis)">
                            <input
                              className={inputClass}
                              placeholder="e.g. 5"
                              value={excessDraftFor(c.id).rate_percent}
                              onChange={(e) => setExcessDrafts((prev) => ({ ...prev, [c.id]: { ...excessDraftFor(c.id), rate_percent: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Flat amount (if flat basis)">
                            <input
                              className={inputClass}
                              placeholder="e.g. 10000"
                              value={excessDraftFor(c.id).flat_amount}
                              onChange={(e) => setExcessDrafts((prev) => ({ ...prev, [c.id]: { ...excessDraftFor(c.id), flat_amount: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Minimum amount (if % basis)">
                            <input
                              className={inputClass}
                              placeholder="e.g. 20000"
                              value={excessDraftFor(c.id).min_amount}
                              onChange={(e) => setExcessDrafts((prev) => ({ ...prev, [c.id]: { ...excessDraftFor(c.id), min_amount: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Label shown to customers">
                            <input
                              className={inputClass}
                              placeholder="Own Damage - 5% of sum insured, min KES 20,000"
                              value={excessDraftFor(c.id).label}
                              onChange={(e) => setExcessDrafts((prev) => ({ ...prev, [c.id]: { ...excessDraftFor(c.id), label: e.target.value } }))}
                            />
                          </Field>
                        </div>
                        <Button variant="ghost" className="mt-3" onClick={() => handleAddExcess(c.id)}>
                          Add excess
                        </Button>
                      </div>
                    )}

                    {/* --- Free benefits --- */}
                    {tab === "free_benefits" && (
                      <div className="mt-4">
                        <p className="text-xs text-ink-soft">
                          What&apos;s already included at no extra cost - windscreen, third party property damage,
                          towing, and so on. Shown to the customer at quote time.
                        </p>
                        {detail.free_benefits.length > 0 && (
                          <table className="mt-3 w-full text-left text-sm">
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
                              {detail.free_benefits.map((b) => (
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

                        <p className="mt-4 text-xs font-medium text-ink-soft">Add a free benefit</p>
                        <div className="mt-2 grid gap-2 sm:grid-cols-3">
                          <Field label="Code" hint="A short id, e.g. windscreen.">
                            <input
                              className={inputClass}
                              placeholder="windscreen"
                              value={freeBenefitDraftFor(c.id).code}
                              onChange={(e) => setFreeBenefitDrafts((prev) => ({ ...prev, [c.id]: { ...freeBenefitDraftFor(c.id), code: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Label shown to customers">
                            <input
                              className={inputClass}
                              placeholder="Windscreen"
                              value={freeBenefitDraftFor(c.id).label}
                              onChange={(e) => setFreeBenefitDrafts((prev) => ({ ...prev, [c.id]: { ...freeBenefitDraftFor(c.id), label: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Limit shown to customers">
                            <input
                              className={inputClass}
                              placeholder="Up to KES 30,000"
                              value={freeBenefitDraftFor(c.id).limit_label}
                              onChange={(e) => setFreeBenefitDrafts((prev) => ({ ...prev, [c.id]: { ...freeBenefitDraftFor(c.id), limit_label: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Top-up note (optional)" hint="What it costs to buy more of this benefit.">
                            <input
                              className={inputClass}
                              placeholder="KES 1,000 per additional KES 10,000"
                              value={freeBenefitDraftFor(c.id).top_up_note}
                              onChange={(e) => setFreeBenefitDrafts((prev) => ({ ...prev, [c.id]: { ...freeBenefitDraftFor(c.id), top_up_note: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Applies to">
                            <select
                              className={inputClass}
                              value={freeBenefitDraftFor(c.id).cover_type}
                              onChange={(e) => setFreeBenefitDrafts((prev) => ({ ...prev, [c.id]: { ...freeBenefitDraftFor(c.id), cover_type: e.target.value } }))}
                            >
                              <option value="comprehensive">Comprehensive</option>
                              <option value="tpo">Third Party Only</option>
                            </select>
                          </Field>
                        </div>
                        <Button variant="ghost" className="mt-3" onClick={() => handleAddFreeBenefit(c.id)}>
                          Add free benefit
                        </Button>
                      </div>
                    )}

                    {/* --- Extra (priced) benefits --- */}
                    {tab === "extensions" && (
                      <div className="mt-4">
                        <p className="text-xs text-ink-soft">
                          Optional extras the customer can add for more cost - courtesy car, excess protector,
                          political violence, and so on. Only add a row here for what this broker actually offers;
                          nothing else needs to be configured to leave an extra out.
                        </p>
                        {detail.extensions.length > 0 && (
                          <table className="mt-3 w-full text-left text-sm">
                            <thead className="text-xs uppercase text-ink-soft">
                              <tr>
                                <th className="pb-2">Benefit</th>
                                <th className="pb-2">Basis</th>
                                <th className="pb-2">Rate / Amount</th>
                                <th className="pb-2">Limit</th>
                                <th className="pb-2" />
                              </tr>
                            </thead>
                            <tbody>
                              {detail.extensions.map((ext) => (
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

                        <p className="mt-4 text-xs font-medium text-ink-soft">Add an extra benefit</p>
                        <div className="mt-2 grid gap-2 sm:grid-cols-4">
                          <Field label="Code" hint="A short id, e.g. courtesy_car.">
                            <input
                              className={inputClass}
                              placeholder="courtesy_car"
                              value={extensionDraftFor(c.id).code}
                              onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), code: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Label shown to customers">
                            <input
                              className={inputClass}
                              placeholder="Loss of use (courtesy car)"
                              value={extensionDraftFor(c.id).label}
                              onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), label: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Priced by">
                            <select
                              className={inputClass}
                              value={extensionDraftFor(c.id).basis}
                              onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), basis: e.target.value } }))}
                            >
                              <option value="flat">Flat amount</option>
                              <option value="percent_of_sum_insured">% of sum insured</option>
                              <option value="per_person">Per person (seating capacity)</option>
                            </select>
                          </Field>
                          <Field label="Rate % (if % basis)">
                            <input
                              className={inputClass}
                              placeholder="e.g. 0.25"
                              value={extensionDraftFor(c.id).rate_percent}
                              onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), rate_percent: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Flat amount (if flat/per-person basis)">
                            <input
                              className={inputClass}
                              placeholder="e.g. 3000"
                              value={extensionDraftFor(c.id).flat_amount}
                              onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), flat_amount: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Minimum amount (if % basis)">
                            <input
                              className={inputClass}
                              placeholder="e.g. 2500"
                              value={extensionDraftFor(c.id).min_amount}
                              onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), min_amount: e.target.value } }))}
                            />
                          </Field>
                          <Field label="Limit shown to customers">
                            <input
                              className={inputClass}
                              placeholder="Up to KES 30,000"
                              value={extensionDraftFor(c.id).limit_label}
                              onChange={(e) => setExtensionDrafts((prev) => ({ ...prev, [c.id]: { ...extensionDraftFor(c.id), limit_label: e.target.value } }))}
                            />
                          </Field>
                        </div>
                        <Button variant="ghost" className="mt-3" onClick={() => handleAddExtension(c.id)}>
                          Add extra benefit
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
      </div>
    </main>
  );
}
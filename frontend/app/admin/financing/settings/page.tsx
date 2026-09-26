"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api, getTokenRole } from "@/lib/api";
import type { FinancingSettings } from "@/lib/types";

type FormState = Record<keyof Omit<FinancingSettings, "updated_at">, string>;

const FIELDS: { key: keyof FormState; label: string; hint?: string; suffix?: string }[] = [
  { key: "deposit_percentage_standard", label: "Standard deposit", suffix: "%" },
  { key: "interest_rate_standard_monthly", label: "Standard interest rate", suffix: "%/month" },
  { key: "interest_rate_preferred_monthly", label: "Preferred interest rate (existing customers)", suffix: "%/month" },
  { key: "min_term_months", label: "Minimum loan term", suffix: "months" },
  { key: "max_term_months", label: "Maximum loan term", suffix: "months" },
  { key: "loan_application_fee_pct", label: "Loan application fee", suffix: "% of financed amount" },
  { key: "life_insurance_fee_pct", label: "Life insurance fee", suffix: "% of financed amount" },
  {
    key: "excise_duty_pct",
    label: "Excise duty",
    suffix: "% of the two fees above",
    hint: "Confirm the current KRA rate before setting this - it defaults to 0% (no charge) until you do.",
  },
  {
    key: "concession_loan_age_max_months",
    label: "Existing-loan concession window",
    suffix: "months",
    hint: "How recent an existing Bidii Credit logbook loan must be for the deposit, rate, and fee waivers to apply.",
  },
];

function toFormState(s: FinancingSettings): FormState {
  return {
    deposit_percentage_standard: s.deposit_percentage_standard,
    interest_rate_standard_monthly: s.interest_rate_standard_monthly,
    interest_rate_preferred_monthly: s.interest_rate_preferred_monthly,
    min_term_months: String(s.min_term_months),
    max_term_months: String(s.max_term_months),
    loan_application_fee_pct: s.loan_application_fee_pct,
    life_insurance_fee_pct: s.life_insurance_fee_pct,
    excise_duty_pct: s.excise_duty_pct,
    concession_loan_age_max_months: String(s.concession_loan_age_max_months),
  };
}

export default function FinancingSettingsPage() {
  const [form, setForm] = useState<FormState | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const role = typeof window !== "undefined" ? getTokenRole() : null;
  const canEdit = role === "management" || role === "super_admin";

  useEffect(() => {
    api
      .get<FinancingSettings>("/api/v1/admin/financing/settings")
      .then((s) => {
        setForm(toFormState(s));
        setUpdatedAt(s.updated_at);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load financing settings"));
  }, []);

  async function save() {
    if (!form) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const payload = {
        deposit_percentage_standard: form.deposit_percentage_standard,
        interest_rate_standard_monthly: form.interest_rate_standard_monthly,
        interest_rate_preferred_monthly: form.interest_rate_preferred_monthly,
        min_term_months: Number(form.min_term_months),
        max_term_months: Number(form.max_term_months),
        loan_application_fee_pct: form.loan_application_fee_pct,
        life_insurance_fee_pct: form.life_insurance_fee_pct,
        excise_duty_pct: form.excise_duty_pct,
        concession_loan_age_max_months: Number(form.concession_loan_age_max_months),
      };
      const updated = await api.patch<FinancingSettings>("/api/v1/admin/financing/settings", payload);
      setForm(toFormState(updated));
      setUpdatedAt(updated.updated_at);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save financing settings");
    } finally {
      setBusy(false);
    }
  }

  if (error && !form) {
    return <main className="mx-auto max-w-2xl px-6 py-12 text-status-error">{error}</main>;
  }
  if (!form) {
    return <main className="mx-auto max-w-2xl px-6 py-12 text-ink-soft">Loading…</main>;
  }

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <Link href="/admin/financing" className="text-sm text-ink-soft hover:underline">
        ← Back to financing portfolio
      </Link>

      <h1 className="mt-3 text-2xl font-bold">Financing settings</h1>
      {/* <p className="mt-1 text-sm text-ink-soft">
        These apply to every new eligibility check and application going forward. Applications already submitted keep
        the rates and fees they were actually given.
      </p> */}
      {updatedAt && <p className="mt-1 text-xs text-ink-soft">Last updated {new Date(updatedAt).toLocaleString()}</p>}

      {!canEdit && (
        <div className="mt-4 rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">
          Only management can change these settings. You can view them below.
        </div>
      )}

      <Card className="mt-6 flex flex-col gap-4">
        {FIELDS.map((field) => (
          <div key={field.key}>
            <label className="block text-sm font-medium text-ink" htmlFor={field.key}>
              {field.label}
            </label>
            <div className="mt-1.5 flex items-center gap-2">
              <input
                id={field.key}
                type="number"
                step="0.01"
                disabled={!canEdit || busy}
                className="w-40 rounded-control border border-neutral-border bg-white px-4 py-2 text-sm text-ink disabled:bg-neutral-tint/40 focus:outline-none focus:ring-2 focus:ring-brand-deep/40 focus:border-brand-deep"
                value={form[field.key]}
                onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
              />
              {field.suffix && <span className="text-sm text-ink-soft">{field.suffix}</span>}
            </div>
            {field.hint && <p className="mt-1 text-xs text-ink-soft">{field.hint}</p>}
          </div>
        ))}

        {error && <p className="text-sm text-status-error">{error}</p>}
        {saved && <p className="text-sm text-status-success">Saved.</p>}

        {canEdit && (
          <Button onClick={save} disabled={busy}>
            {busy ? "Saving…" : "Save changes"}
          </Button>
        )}
      </Card>
    </main>
  );
}
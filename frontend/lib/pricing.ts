// Types and small helpers for the two staff-configurable pricing features: Bidii
// Credit IPF rate tiers and anniversary alignment. Data comes from
// backend app/api/v1/admin_pricing.py. No React in here.

export interface RateTier {
  id: string;
  label: string;
  applies_to: "all" | "individual" | "corporate";
  min_amount: string;
  max_amount: string | null;
  min_term_months: number;
  max_term_months: number | null;
  interest_rate_monthly: string;
  is_active: boolean;
}

export interface RatePreview {
  rate: string;
  source: "tier" | "corporate" | "standard";
  tier: RateTier | null;
  standard_rate: string;
}

export interface AnniversarySettings {
  enabled: boolean;
  method: "pro_rata_daily" | "short_period_scale";
  year_basis_days: number;
  minimum_premium_pct: string;
  min_stub_days: number;
  max_term_days: number;
}

export interface ScaleBand {
  id: string;
  provider_id: string | null;
  provider_name: string | null;
  up_to_days: number;
  percent_of_annual: string;
}

export interface ProviderLite {
  id: string;
  name: string;
}

export interface PremiumPreview {
  term_days: number;
  premium: string;
  method_used: string;
  percent_of_annual: string;
}

export interface PolicyAlignment {
  policy_id: string;
  policy_number: string;
  provider_name: string | null;
  end_date: string;
  annual_premium: string;
  strategy: "already_aligned" | "short_period" | "long_period";
  new_start: string;
  new_end: string;
  term_days: number;
  stub_days: number;
  very_short: boolean;
  note: string;
  estimated_premium: string;
  method_used: string;
  percent_of_annual: string;
}

export interface CustomerPlan {
  customer_id: string;
  customer_name: string;
  enabled: boolean;
  anniversary_date: string | null;
  notes: string | null;
  suggested_anniversary: string | null;
  using_suggestion: boolean;
  policies: PolicyAlignment[];
}

export interface CustomerLookup {
  id: string;
  full_name: string;
  phone: string | null;
  active_policies: number;
  anniversary_date: string | null;
}

export interface AnniversaryListItem {
  customer_id: string;
  customer_name: string;
  anniversary_date: string;
  active_policies: number;
}

export interface RenewalAlignment {
  anniversary_date: string;
  strategy: PolicyAlignment["strategy"];
  new_end: string;
  term_days: number;
  estimated_premium: string;
  very_short: boolean;
  note: string;
}

export const STRATEGY_LABEL: Record<PolicyAlignment["strategy"], string> = {
  already_aligned: "Already aligned",
  short_period: "Short period",
  long_period: "Long period",
};

export const METHOD_LABEL: Record<AnniversarySettings["method"], string> = {
  pro_rata_daily: "Pro-rata by the day",
  short_period_scale: "Insurer's short-period table",
};

export const APPLIES_LABEL: Record<RateTier["applies_to"], string> = {
  all: "Everyone",
  individual: "Individuals",
  corporate: "Companies",
};

export function kes(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return "-";
  const n = Number(amount);
  return Number.isNaN(n) ? String(amount) : `KES ${n.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

export function day(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" });
}

/** "KES 100,000 to under KES 500,000" / "KES 500,000 and above". */
export function amountRange(tier: Pick<RateTier, "min_amount" | "max_amount">): string {
  return tier.max_amount === null ? `${kes(tier.min_amount)} and above` : `${kes(tier.min_amount)} to under ${kes(tier.max_amount)}`;
}

/** "3-10 months" / "6+ months". */
export function termRange(tier: Pick<RateTier, "min_term_months" | "max_term_months">): string {
  return tier.max_term_months === null ? `${tier.min_term_months}+ months` : `${tier.min_term_months}-${tier.max_term_months} months`;
}

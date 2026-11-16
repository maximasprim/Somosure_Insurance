/** Types and small helpers for the weekly sales report import (/admin/sales-import). */

export const BASE = "/api/v1/admin/sales-import";

export const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export interface Counts {
  new: number;
  updated: number;
  unchanged: number;
  restored: number;
  missing: number;
  total: number;
}

export interface ReconRow {
  sheet: string;
  year: number;
  month: number | null;
  rows: number;
  premium: string;
  commission: string;
  sheet_premium: string | null;
  sheet_commission: string | null;
  difference: Record<string, string>;
  status: "ok" | "mismatch" | "no_total";
}

export interface ImportIssue {
  severity: "error" | "warning";
  code: string;
  sheet: string;
  row: number;
  month: number | null;
  client_name: string | null;
  policy_number: string | null;
  message: string;
}

export interface ImportChange {
  kind: string;
  sheet: string | null;
  row: number | null;
  client_name: string | null;
  policy_number: string | null;
  fields: { field: string; old: string | null; new: string | null }[];
}

export interface MissingRow {
  kind: string;
  sheet: string | null;
  row: number | null;
  client_name: string | null;
  policy_number: string | null;
}

export interface ImportReport {
  dry_run: boolean;
  filename: string | null;
  already_imported: boolean;
  batch_id: string | null;
  sheets: { name: string; kind: string; year: number; rows: number }[];
  ignored_sheets: string[];
  notes: string[];
  unknown_columns: Record<string, string[]>;
  counts: { sales: Counts; claims: Counts; ipf: Counts };
  totals: { rows: number; premium: string; commission: string };
  reconciliation: ReconRow[];
  issue_counts: Record<string, { severity: "error" | "warning" | "info"; count: number }>;
  issues: ImportIssue[];
  issues_total: number;
  changes: ImportChange[];
  changes_total: number;
  missing: MissingRow[];
  missing_total: number;
  new_aliases: {
    underwriters: { typed: string; canonical: string }[];
    staff: { typed: string; name: string | null; branch: string | null }[];
  };
  period: { from: string | null; to: string | null; skipped: { sales: number; claims: number; ipf: number } };
  posting?: { resynced?: { checked: number; policies: number; payments: number; customers: number }; posted?: { posted: number; customers_created: number; held: Record<string, number> } | null; error?: string } | null;
  customer_links?: { linked_by_policy: number; linked_by_phone: number; linked_by_plate: number; claims_linked: number; clients_without_phone: number } | null;
}

export interface Suggestion {
  entry_id: string;
  client_name: string;
  policy_number: string | null;
  underwriter: string | null;
  sheet: string;
  row: number | null;
  field: "start_date" | "expiry_date";
  label: string;
  current: string | null;
  suggested: string;
  reason: string | null;
  start_date: string | null;
  expiry_date: string | null;
  date_paid: string | null;
}

export interface Flag {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
}

export interface SalesEntry {
  id: string;
  sheet_name: string;
  sheet_year: number;
  sheet_row: number | null;
  period_year: number;
  period_month: number | null;
  client_name: string;
  phone: string | null;
  underwriter: string | null;
  reg_no: string | null;
  asset_ref: string | null;
  product_line: string;
  start_date: string | null;
  expiry_date: string | null;
  date_paid: string | null;
  staff_name: string | null;
  branch: string | null;
  business_type: string | null;
  policy_number: string | null;
  cover_type: string | null;
  premium: string | null;
  commission: string | null;
  wht: string | null;
  net_revenue: string | null;
  flags: Flag[] | null;
  issue_level: "none" | "info" | "warning" | "error";
  status: "active" | "missing_from_sheet";
  policy_id: string | null;
}

export interface EntryPage {
  total: number;
  premium: string;
  commission: string;
  items: SalesEntry[];
}

export interface EntryOptions {
  years: number[];
  underwriters: string[];
  staff: string[];
  branches: string[];
  products: string[];
}

export interface Alias {
  id: string;
  kind: "underwriter" | "staff";
  alias_key: string;
  as_typed: string | null;
  canonical: string | null;
  branch: string | null;
  confirmed: boolean;
  source: string;
}

export interface Milestone {
  event: string;
  date: string;
}

export interface LegacyClaim {
  id: string;
  period_year: number;
  client_name: string;
  contact: string | null;
  reg_or_policy: string | null;
  underwriter: string | null;
  date_reported: string | null;
  narrative: string | null;
  outcome: string;
  milestones: Milestone[] | null;
  sales_entry_id: string | null;
  status: string;
}

export interface IpfRow {
  id: string;
  period_year: number;
  underwriter: string | null;
  details: string | null;
  date_paid: string | null;
  amount: string | null;
  status: string;
}

export interface GroupRow {
  count: number;
  premium: string;
  commission: string;
  [key: string]: string | number | null;
}

export interface Summary {
  year: number;
  monthly: { year: number; month: number | null; count: number; premium: string; commission: string }[];
  by_underwriter: GroupRow[];
  by_staff: GroupRow[];
  by_branch: GroupRow[];
  by_business_type: GroupRow[];
  by_product: GroupRow[];
  expiring: {
    id: string;
    client_name: string;
    phone: string | null;
    underwriter: string | null;
    reg_no: string | null;
    asset_ref: string | null;
    expiry_date: string;
    premium: string | null;
    staff_name: string | null;
    branch: string | null;
  }[];
  expiring_window_days: number;
}

export const ISSUE_LABELS: Record<string, string> = {
  date_day_month_swapped: "Day and month swapped back (corrected)",
  dates_unverified: "Date order could not be confirmed",
  date_missing: "Date missing",
  date_unreadable: "Date could not be read",
  expiry_before_start: "Expiry is before the start date",
  period_over_a_year: "Policy period longer than a year",
  period_under_a_year: "Policy period shorter than a year",
  paid_long_after_start: "Paid long after the start date",
  premium_missing: "Premium missing",
  premium_not_a_number: "Premium is not a number",
  premium_not_positive: "Premium is zero or negative",
  commission_missing_or_zero: "Commission missing or zero",
  commission_over_30pct: "Commission over 30% of premium",
  commission_rate_differs: "Commission rate differs from the insurer's usual",
  policy_number_missing: "Policy number missing",
  reg_missing: "Registration / product missing",
  reg_unusual: "Unusual registration",
  business_type_missing: "New business / renewal not filled in",
  underwriter_unknown: "Underwriter not recognised",
  underwriter_fuzzy_match: "Underwriter spelling matched",
  underwriter_missing: "Underwriter missing",
  staff_missing: "Staff / branch missing",
  duplicate_in_sheet: "Policy number repeated in the same year",
  month_inferred: "Month worked out from the block before it",
  phone_unreadable: "Phone number could not be read",
  amount_missing: "Amount missing",
  fix_applied: "Suggested date fix accepted",
};

export const PRODUCT_LABELS: Record<string, string> = {
  motor: "Motor",
  professional_indemnity: "Professional indemnity",
  medical: "Medical",
  wiba: "WIBA",
  bid_bond: "Bid bond",
  credit_life: "Credit life",
  personal_accident: "Personal accident",
  life: "Life",
  travel: "Travel",
  property: "Property",
  additions: "Additions",
  other: "Other",
  unknown: "Not stated",
};

export const OUTCOME_LABELS: Record<string, string> = {
  open: "Open",
  closed: "Closed",
  closed_unresponsive: "Closed - client unresponsive",
  action_needed: "Action needed",
};

export const EVENT_LABELS: Record<string, string> = {
  reported: "Reported",
  documents_submitted: "Documents submitted",
  assessment: "Assessed",
  repair_authority: "Repair authority",
  release_letter: "Release letter",
  discharge_voucher: "Discharge voucher",
  lpo_issued: "LPO issued",
  repairs_done: "Repairs done",
  cash_in_lieu: "Cash in lieu",
  payment: "Payment / refund",
  note: "Note",
};

export function kes(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "-";
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("en-KE", { maximumFractionDigits: 0 }) : "-";
}

export function dmy(value: string | null | undefined): string {
  if (!value) return "-";
  const [y, m, d] = value.slice(0, 10).split("-");
  return d && m && y ? `${d}/${m}/${y}` : value;
}

export function monthLabel(month: number | null | undefined): string {
  return month ? MONTHS[month - 1] : "-";
}

/** "2025-01" -> "January 2025" */
export function periodLabel(period: string | null | undefined): string {
  if (!period) return "";
  const [y, m] = period.split("-");
  return `${MONTHS[Number(m) - 1] ?? m} ${y}`;
}


// ---- posting into the system's own tables -------------------------------------------------------

export const POST_BASE = "/api/v1/admin/sales-import/posting";

export interface PostingStatus {
  ready: number;
  held: Record<string, number>;
  held_total: number;
  flags_on_ready: Record<string, number>;
  posted: number;
  matched_to_platform_policies: number;
  posted_flags: Record<string, number>;
  unlinked_underwriters: { underwriter: string; rows: number }[];
}

export interface UnderwriterRow {
  underwriter: string;
  rows: number;
  posted: number;
  premium: string;
  provider_id: string | null;
  provider_name: string | null;
  provider_status: string | null;
  source: string | null;
  linked: boolean;
}

export interface ProviderOption {
  id: string;
  name: string;
  status: string;
}

export interface HeldRow {
  id: string;
  client_name: string;
  underwriter: string | null;
  policy_number: string | null;
  sheet: string | null;
  row: number | null;
  premium: string | null;
  start_date: string | null;
  expiry_date: string | null;
  reasons: { code: string; message: string }[];
}

export interface ReviewRow {
  id: string;
  client_name: string;
  underwriter: string | null;
  policy_number: string | null;
  sheet: string | null;
  row: number | null;
  policy_id: string | null;
  customer_id: string | null;
  flags: { code: string; message: string }[];
}

export interface PostResult {
  dry_run: boolean;
  to_post?: number;
  posted?: number;
  customers_created?: number;
  held: Record<string, number>;
  flags: Record<string, number>;
  resynced?: { checked: number; policies: number; payments: number; customers: number };
}

export const POST_FLAG_LABELS: Record<string, string> = {
  customer_no_phone: "No phone number (customer saved with a blank phone)",
  customer_matched_by_name: "Customer matched by name only",
  policy_number_placeholder: "No policy number - a placeholder is used",
  policy_number_year_added: "Policy number already in use - year added",
  date_assumed: "A start or expiry date was assumed",
  payment_date_assumed: "Payment date assumed",
  import_issues: "The sheet row has problems",
};

export const HELD_LABELS: Record<string, string> = {
  no_provider_link: "Underwriter not linked to a provider",
  no_underwriter: "No underwriter on the row",
  missing_premium: "No premium",
  missing_dates: "No start or expiry date",
};

export interface PostingOverview {
  status: PostingStatus;
  held: { total: number; items: HeldRow[] };
  review: { total: number; items: ReviewRow[] };
  underwriters: { underwriters: UnderwriterRow[]; providers: ProviderOption[] };
}

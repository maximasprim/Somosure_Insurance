/** Types and helpers for the views that show platform sales and weekly-report-workbook sales together:
 *  /admin/sales, the "All sales" part of the dashboard, and a customer's workbook history. */

import type { KpiValue, NamedCount } from "@/lib/analytics";
import type { LegacyClaim, SalesEntry } from "@/lib/salesImport";

export const SALES_BASE = "/api/v1/admin/sales";

export interface WorkbookAnalytics {
  kpis: Record<string, KpiValue>;
  sources: NamedCount[];
  monthly: { date: string; sales: number; premium: number; commission: number }[];
  by_underwriter: NamedCount[];
  by_branch: NamedCount[];
  by_staff: NamedCount[];
  by_business_type: NamedCount[];
  by_product: NamedCount[];
  claims: NamedCount[];
  renewals: { due_60d: number; overdue_30d: number };
  customers: { workbook_clients: number; linked_to_customers: number };
  coverage: { workbook_from: string | null; workbook_to: string | null; last_import: string | null };
}

export interface UnifiedSale {
  source: "platform" | "workbook" | "manual" | "platform+workbook";
  id: string;
  sold_on: string | null;
  client_name: string | null;
  phone: string | null;
  underwriter: string | null;
  reg_no: string | null;
  product: string | null;
  policy_number: string | null;
  premium: string | null;
  commission: string | null;
  wht: string | null;
  net_revenue: string | null;
  staff: string | null;
  branch: string | null;
  business_type: string | null;
  start_date: string | null;
  expiry_date: string | null;
  status: string | null;
  customer_id: string | null;
}

export interface UnifiedSalesPage {
  total: number;
  premium: string;
  commission: string;
  items: UnifiedSale[];
}

export interface SalesOptions {
  years: number[];
  underwriters: string[];
  staff: string[];
  branches: string[];
  products: string[];
}

export interface RenewalItem {
  source: "platform" | "workbook";
  id: string;
  expiry_date: string | null;
  days_left: number | null;
  client_name: string | null;
  phone: string | null;
  customer_id: string | null;
  underwriter: string | null;
  reg_no: string | null;
  premium: string | null;
  staff: string | null;
  branch: string | null;
  status: string;
  note: string | null;
  policy_number: string | null;
}

export interface RenewalPage {
  total: number;
  items: RenewalItem[];
}

export interface CustomerStatus {
  clients: number;
  linked: number;
  unlinked_with_phone: number;
  unlinked_without_phone: number;
}

export interface LinkResult {
  linked_by_policy: number;
  linked_by_phone: number;
  linked_by_plate: number;
  customers_created: number;
  policies_waiting_for_a_customer: number;
  customers_that_would_be_created: number;
  clients_without_phone: number;
  claims_linked: number;
}

export interface NeedsPhoneRow {
  client_key: string;
  client_name: string;
  policies: number;
  premium: string;
  latest_expiry: string | null;
  sample_reg: string | null;
}

export interface CustomerHistory {
  entries: SalesEntry[];
  claims: LegacyClaim[];
}

export const SOURCE_LABELS: Record<string, string> = {
  platform: "Platform",
  workbook: "Workbook",
  manual: "Entered in system",
  "platform+workbook": "Platform + workbook",
};

export const FOLLOW_UP_LABELS: Record<string, string> = {
  due: "Due",
  contacted: "Contacted",
  quoted: "Quoted",
  renewed: "Renewed",
  lost: "Lost",
  paid: "Paid",
};

/** wa.me wants digits only: +254 712 345 678 -> 254712345678. Returns null if it is not a usable number. */
export function whatsappLink(phone: string | null | undefined, text?: string): string | null {
  const digits = (phone ?? "").replace(/\D/g, "");
  const full = digits.length === 10 && digits.startsWith("0") ? `254${digits.slice(1)}` : digits;
  if (full.length < 11) return null;
  return `https://wa.me/${full}${text ? `?text=${encodeURIComponent(text)}` : ""}`;
}


// ---- recording a sale directly in the system ---------------------------------------------------------

export interface RecordProvider {
  id: string;
  name: string;
  status: string;
  underwriter: string;
  typical_commission_rate: string | null;
}

export interface RecordOptions {
  providers: RecordProvider[];
  staff: string[];
  branches: string[];
  product_hints: string[];
  wht_rate: string;
}

export interface RecordResult {
  created: boolean;
  duplicates?: { where: string; what: string }[];
  entry_id?: string;
  policy_id?: string;
  policy_number?: string;
  customer_id?: string;
  customer_existed?: boolean;
  flags?: { code: string; message: string }[];
}

export interface RecentSale {
  id: string;
  client_name: string;
  underwriter: string | null;
  policy_number: string | null;
  premium: string | null;
  date_paid: string | null;
  staff_name: string | null;
  branch: string | null;
  policy_id: string | null;
  customer_id: string | null;
  post_flags: { code: string; message: string }[] | null;
  created_at: string;
}

export interface CustomerHit {
  id: string;
  full_name: string;
  phone: string | null;
}

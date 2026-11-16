/** Types for the admin Customers list (/admin/customers). */

export const CUSTOMER_LIST = "/api/v1/admin/customer-list";

export interface CustomerRow {
  id: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  lead_source: string | null;
  created_at: string | null;
  policies: number;
  active_policies: number;
  premium: string;
  next_expiry: string | null;
  has_workbook: boolean;
}

export interface CustomerPage {
  total: number;
  items: CustomerRow[];
  stats: { customers: number; with_active_policy: number; without_phone: number; from_workbook: number };
  sources: string[];
}

export const SOURCE_NAMES: Record<string, string> = {
  workbook: "Weekly report workbook",
  website: "Website",
  whatsapp: "WhatsApp",
  referral: "Referral",
  agent: "Agent",
};

export function sourceName(source: string | null): string {
  if (!source) return "Not recorded";
  return SOURCE_NAMES[source] ?? source.charAt(0).toUpperCase() + source.slice(1).replace(/_/g, " ");
}

// Types and wording for the Bidii Credit IPF extras: early settlement, post-dated
// cheques, linked/unlinked IPF with a vehicle tracker, the original logbook, and
// loan officers with their commission. Data comes from the endpoints in
// backend app/api/v1/admin_ipf.py. Pure types and small helpers, no React.

export interface LoanOfficer {
  id: string;
  full_name: string;
  staff_number: string;
  email: string | null;
  phone: string | null;
  monthly_target: string | null;
  is_active: boolean;
}

export interface LoanOfficerSummary extends LoanOfficer {
  financed_this_month: string;
  requests_this_month: number;
  target_progress_pct: number | null;
  commission_pending: string;
  commission_approved: string;
  commission_paid: string;
}

export interface OfficerCommission {
  id: string;
  loan_officer_id: string;
  loan_officer_name: string | null;
  financing_application_id: string;
  financing_reference: string | null;
  policy_id: string | null;
  policy_number: string | null;
  somosure_net_commission: string | null;
  rate_pct: string;
  commission_amount: string | null;
  status: "awaiting_basis" | "pending" | "approved" | "paid" | "cancelled";
  approved_at: string | null;
  paid_at: string | null;
  payout_reference: string | null;
  created_at: string;
}

export interface Cheque {
  id: string;
  cheque_number: string;
  bank_name: string;
  amount: string;
  cheque_date: string;
  status: "received" | "banked" | "bounced" | "returned";
  notes: string | null;
  received_at: string;
}

export interface SettlementQuote {
  eligible: boolean;
  reason: string | null;
  instalments_remaining: number;
  outstanding_principal: string;
  fee_pct: string;
  fee_amount: string;
  total_due: string;
  would_have_paid: string;
  saving: string;
  capped: boolean;
}

export interface Settlement {
  id: string;
  instalments_remaining: number;
  outstanding_principal: string;
  fee_pct: string;
  fee_amount: string;
  total_paid: string;
  would_have_paid: string;
  payment_reference: string | null;
  notes: string | null;
  settled_at: string;
}

export interface IpfDetail {
  ipf_type: "linked" | "unlinked";
  loan_officer: LoanOfficer | null;
  commission: OfficerCommission | null;
  tracker: { required: boolean; installed: boolean; provider: string | null; device_id: string | null; installed_at: string | null };
  original_logbook_received_at: string | null;
  cheques_required: number;
  cheques_received: number;
  cheques: Cheque[];
  early_settlement: SettlementQuote | null;
  settlement: Settlement | null;
}

export const COMMISSION_LABELS: Record<OfficerCommission["status"], string> = {
  awaiting_basis: "Needs net commission",
  pending: "Pending approval",
  approved: "Approved",
  paid: "Paid",
  cancelled: "Cancelled",
};

export const IPF_TYPE_HELP: Record<IpfDetail["ipf_type"], string> = {
  unlinked:
    "Stand-alone IPF. The client pays the deposit and hands over one post-dated cheque for each monthly repayment.",
  linked:
    "The client also has a Bidii Credit auto loan. The vehicle carries a tracker and is held under that loan, so cheques aren't needed.",
};

export function formatDay(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" });
}

export function kes(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return "-";
  const n = Number(amount);
  return Number.isNaN(n) ? String(amount) : `KES ${n.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

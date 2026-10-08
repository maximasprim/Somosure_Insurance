export interface FreeBenefit {
  code: string;
  label: string;
  limit_label: string | null;
  top_up_note: string | null;
}

export interface PaymentScheduleLeg {
  sequence: number;
  kind: "full" | "deposit" | "installment";
  due_date: string;
  amount: string;
  cover_from?: string;
  cover_to?: string;
}

export interface PaymentPlanOption {
  plan_code: string;
  label: string;
  type: "full" | "installments";
  installments: number;
  deposit_percent: string;
  due_now: string;
  sticker_months_per_payment: number | null;
  schedule: PaymentScheduleLeg[];
}

export interface ExtraBenefitCatalogItem {
  code: string;
  label: string;
}

export interface NormalizedQuote {
  id: string;
  provider_id: string;
  provider_name: string;
  underlying_provider_name: string | null;
  premium: string;
  taxes: string;
  fees: string;
  total: string;
  currency: string;
  coverage: Record<string, unknown> & { free_benefits?: FreeBenefit[]; assumptions?: string[] };
  exclusions: Record<string, unknown>;
  deductibles: Record<string, unknown>;
  payment_options: Record<string, unknown> & { plans?: PaymentPlanOption[] };
  provider_metadata: Record<string, unknown>;
  is_mock: boolean;
  valid_until: string | null;
}

export interface QuoteRequestResult {
  reference: string;
  category: string;
  status: string;
  customer_id: string | null;
  quotes: NormalizedQuote[];
  note: string | null;
}

export interface ApplicationResult {
  id: string;
  reference: string;
  quote_id: string;
  status: string;
  provider_reference: string | null;
  created_at: string;
}

export interface ApplicationEvent {
  id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  notes: string | null;
  created_at: string;
}

export interface ApplicationDocument {
  id: string;
  document_type: string;
  original_filename: string;
  status: string;
  uploaded_at: string;
  validation_notes?: string | null;
}

export interface ApplicationCustomer {
  id: string;
  full_name: string;
  email: string | null;
  phone: string;
  id_number: string | null;
  kra_pin: string | null;
}

export interface ApplicationVehicle {
  id: string;
  registration_number: string;
  chassis_number: string | null;
  engine_number: string | null;
  make: string;
  model: string;
  year: number;
  value: string;
  usage: string;
}

export interface ApplicationInsuredAsset {
  id: string;
  category: string;
  description: string | null;
  value: string | null;
  details: Record<string, unknown>;
}

export interface ApplicationQuote {
  id: string;
  provider_name: string;
  underlying_provider_name: string | null;
  product_name: string | null;
  premium: string;
  taxes: string;
  fees: string;
  total: string;
  currency: string;
  coverage: Record<string, unknown>;
  exclusions: Record<string, unknown>;
  deductibles: Record<string, unknown>;
  is_mock: boolean;
}

export interface ApplicationDetail {
  id: string;
  reference: string;
  status: string;
  applicant_details: Record<string, unknown>;
  provider_reference: string | null;
  created_at: string;
  updated_at: string;
  customer: ApplicationCustomer;
  quote: ApplicationQuote;
  vehicle: ApplicationVehicle | null;
  insured_asset: ApplicationInsuredAsset | null;
  documents: ApplicationDocument[];
  events: ApplicationEvent[];
}

export interface PaymentInitiateResult {
  payment_id: string;
  reference: string;
  status: string;
  provider_transaction_id: string;
  is_mock: boolean;
  plan_code?: string | null;
  installment_sequence?: number | null;
  remaining_schedule?: PaymentScheduleLeg[] | null;
}

export interface PaymentStatusResult {
  id: string;
  reference: string;
  amount: string;
  currency: string;
  method: string;
  status: string;
  created_at: string;
}

export interface CustomerProfile {
  id: string;
  full_name: string;
  email: string | null;
  phone: string;
  id_number: string | null;
  kra_pin: string | null;
  consent_marketing: boolean;
}

export interface PolicySummary {
  id: string;
  policy_number: string;
  status: string;
  payment_status: string;
  premium: string;
  start_date: string;
  end_date: string;
  is_mock: boolean;
}

export interface DashboardData {
  active_policies: PolicySummary[];
  pending_applications: ApplicationResult[];
  upcoming_renewals: PolicySummary[];
  outstanding_payments: PaymentStatusResult[];
}

export interface SupportTicket {
  id: string;
  reference: string;
  category: string;
  subject: string;
  status: string;
  created_at: string;
}

export interface Lead {
  id: string;
  customer_id: string;
  stage: string;
  source: string;
  product_interest: string | null;
  assigned_agent_id: string | null;
  quote_request_id: string | null;
  created_at: string;
  updated_at: string;
  customer_name: string;
  customer_phone: string;
}

export interface LeadActivity {
  id: string;
  activity_type: string;
  notes: string | null;
  created_at: string;
}

export interface FunnelData {
  stages: { stage: string; count: number }[];
  total: number;
}

export interface StickerRecord {
  id: string;
  reference: string;
  policy_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AutomationRule {
  id: string;
  name: string;
  trigger_event: string;
  conditions: Record<string, unknown>;
  action_type: string;
  action_config: Record<string, unknown>;
  delay_seconds: number;
  is_active: boolean;
}

export interface AutomationRun {
  id: string;
  rule_id: string;
  trigger_event: string;
  entity_type: string;
  entity_id: string;
  status: string;
  scheduled_for: string;
  executed_at: string | null;
  result: Record<string, unknown>;
  error: string | null;
}

export interface AppNotification {
  id: string;
  channel: string;
  event_type: string;
  subject: string | null;
  body: string;
  status: string;
  is_read: boolean;
  created_at: string;
}

export interface EligibilityResult {
  eligible: boolean;
  reason: string | null;
  total_premium: string;
  deposit_percentage: string;
  deposit_amount: string;
  financed_amount: string;
  interest_rate_monthly: string;
  concession_applied: boolean;
  corporate_terms_applied?: boolean;
  loan_application_fee: string | null;
  life_insurance_fee: string | null;
  excise_duty_amount: string | null;
  total_repayable: string | null;
  term_months: number;
  monthly_installment: string | null;
  is_mock: boolean;
  // Live admin-configured context (additive - older responses omit these).
  concession_loan_age_max_months?: number | null;
  min_term_months?: number | null;
  max_term_months?: number | null;
  standard_deposit_percentage?: string | null;
  standard_interest_rate_monthly?: string | null;
  preferred_interest_rate_monthly?: string | null;
}

export interface FinancingApplicationResult {
  id: string;
  reference: string;
  status: string;
  total_premium: string;
  deposit_percentage: string;
  deposit_amount: string;
  financed_amount: string;
  interest_rate_monthly: string;
  concession_applied: boolean;
  loan_application_fee: string;
  life_insurance_fee: string;
  excise_duty_amount: string;
  total_repayable: string;
  term_months: number;
  has_existing_logbook_loan: boolean;
  logbook_loan_age_months: number | null;
  is_corporate: boolean;
  provider_reference: string | null;
  rejection_reason: string | null;
  created_at: string;
}

export interface FinancingDocument {
  id: string;
  document_type: string;
  original_filename: string;
  status: string;
  uploaded_at: string;
  validation_notes?: string | null;
}

export interface FinancingEvent {
  id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  notes: string | null;
  created_at: string;
}

export interface FinancingInstallmentResult {
  id: string;
  installment_number: number;
  due_date: string;
  amount: string;
  status: string;
  paid_at: string | null;
}

export interface FinancingAgreementResult {
  id: string;
  application_id: string;
  financed_amount: string;
  interest_rate_monthly: string;
  total_repayable: string;
  term_months: number;
  monthly_installment: string;
  status: string;
  installments: FinancingInstallmentResult[];
}

export interface FinancingCustomer {
  id: string;
  full_name: string;
  email: string | null;
  phone: string;
  id_number: string | null;
  kra_pin: string | null;
}

export interface FinancingQuote {
  id: string;
  provider_name: string;
  product_name: string | null;
  premium: string;
  total: string;
  currency: string;
}

export interface FinancingApplicationDetail {
  id: string;
  reference: string;
  status: string;
  customer: FinancingCustomer;
  quote: FinancingQuote;
  total_premium: string;
  deposit_percentage: string;
  deposit_amount: string;
  financed_amount: string;
  interest_rate_monthly: string;
  concession_applied: boolean;
  loan_application_fee_pct: string;
  loan_application_fee: string;
  life_insurance_fee_pct: string;
  life_insurance_fee: string;
  excise_duty_pct: string;
  excise_duty_amount: string;
  total_repayable: string;
  term_months: number;
  has_existing_logbook_loan: boolean;
  logbook_loan_age_months: number | null;
  is_corporate: boolean;
  provider_reference: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
  documents: FinancingDocument[];
  events: FinancingEvent[];
  agreement: FinancingAgreementResult | null;
}

export interface FinancingSettings {
  deposit_percentage_standard: string;
  interest_rate_standard_monthly: string;
  interest_rate_preferred_monthly: string;
  min_term_months: number;
  max_term_months: number;
  loan_application_fee_pct: string;
  life_insurance_fee_pct: string;
  excise_duty_pct: string;
  concession_loan_age_max_months: number;
  corporate_deposit_percentage?: string | null;
  corporate_interest_rate_monthly?: string | null;
  updated_at: string;
}

export interface ReportOverview {
  customers: { total: number; new_this_month: number };
  leads: { total: number; won: number };
  quotes: { requests: number; quotes_returned: number; conversion_rate_pct: number | null };
  policies: { total: number; active: number; total_active_premium: string };
  revenue: { collected: string; commission: string; outstanding_payment_count: number };
  renewals: { due: number; renewed: number };
  stickers_by_status: Record<string, number>;
  claims: { total: number; open: number; by_status: Record<string, number> };
}

export interface ProviderPerformance {
  provider_id: string;
  name: string;
  provider_type: string;
  status: string;
  quotes_returned: number;
  policies_issued: number;
}

export interface Claim {
  id: string;
  reference: string;
  policy_id: string;
  status: string;
  incident_date: string;
  incident_description: string;
  incident_location: string | null;
  provider_reference: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClaimEvent {
  id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  notes: string | null;
  created_at: string;
}

// --- Quote-journey helpers (document checklist, availability) ---

export interface DocumentRequirement {
  type: string;
  label: string;
  description: string;
  tips: string[];
  system_provided: boolean;
}

export interface DocumentRequirements {
  category: string;
  accepted_formats: string;
  max_mb: number;
  general_tips: string[];
  insurance: DocumentRequirement[];
  financing: { note: string; documents: DocumentRequirement[] };
}

export interface ChecklistItem {
  type: string;
  label: string;
  description: string;
  tips: string[];
  state: "provided" | "missing" | "auto";
  source: "uploaded" | "insurance_application" | "earlier_application" | "generated" | null;
}

export interface DocumentChecklist {
  items: ChecklistItem[];
  missing: string[];
  complete: boolean;
}

export interface CategoryAvailability {
  available: boolean;
  mode: "live" | "demo" | "coming_soon";
}

// --- Audit trail ---

export interface AuditEntry {
  id: string;
  seq: number;
  occurred_at: string;
  kind: "change" | "request" | "event";
  action: string;
  actor_type: "staff" | "customer" | "guest" | "system";
  actor_user_id: string | null;
  actor_name: string | null;
  actor_email: string | null;
  actor_role: string | null;
  entity_type: string | null;
  entity_id: string | null;
  entity_label: string | null;
  related_customer_id: string | null;
  summary: string | null;
  reason: string | null;
  changes: Record<string, [unknown, unknown]> | null;
  details: Record<string, unknown> | null;
  request_id: string | null;
  method: string | null;
  path: string | null;
  status_code: number | null;
  duration_ms: number | null;
  ip: string | null;
  user_agent: string | null;
}

export interface AuditPage {
  items: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditFacets {
  entity_types: string[];
  actions: string[];
}

// --- Affiliate program ---

export interface AffiliateSettings {
  program_enabled: boolean;
  default_rate_type: "percent" | "fixed";
  default_rate_value: string;
  min_premium: string | null;
  max_commission_per_policy: string | null;
  scope: "first_policy" | "all_policies";
  window_months: number;
  auto_approve: boolean;
  allow_self_enrollment: boolean;
  updated_at: string;
}

export interface AffiliateRateRule {
  id: string;
  name: string;
  rate_type: "percent" | "fixed";
  rate_value: string;
  max_amount: string | null;
  affiliate_customer_id: string | null;
  affiliate_name: string | null;
  category: string | null;
  starts_on: string | null;
  ends_on: string | null;
  active: boolean;
  created_at: string;
}

export interface AffiliatePartner {
  id: string;
  customer_id: string;
  customer_name: string | null;
  customer_phone: string | null;
  code: string;
  status: "active" | "suspended";
  payout_method: string;
  payout_phone: string | null;
  notes: string | null;
  referred: number;
  converted: number;
  earned_pending: string;
  earned_approved: string;
  earned_paid: string;
  created_at: string;
}

export type CommissionStatus = "pending" | "approved" | "paid" | "reversed" | "rejected";

export interface AffiliateCommissionRow {
  id: string;
  referrer_customer_id: string;
  referrer_name: string | null;
  referrer_phone: string | null;
  payout_phone: string | null;
  referred_name: string | null;
  policy_id: string | null;
  policy_number: string | null;
  category: string | null;
  premium: string;
  rate_type: string;
  rate_value: string;
  rate_label: string | null;
  commission_amount: string;
  status: CommissionStatus;
  status_note: string | null;
  approved_at: string | null;
  paid_at: string | null;
  payout_method: string | null;
  payout_reference: string | null;
  created_at: string;
}

export interface AffiliateCommissionPage {
  items: AffiliateCommissionRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface AffiliateSummary {
  pending_count: number;
  pending_amount: string;
  approved_count: number;
  approved_amount: string;
  paid_count: number;
  paid_amount: string;
  affiliates: number;
  referred: number;
  converted: number;
}

export interface MyAffiliate {
  program_enabled: boolean;
  can_self_enroll: boolean;
  is_affiliate: boolean;
  affiliate_code: string | null;
  affiliate_status: string | null;
  payout_phone: string | null;
  referred: number;
  converted: number;
  earned_pending: string;
  earned_approved: string;
  earned_paid: string;
  commissions: {
    id: string;
    category: string | null;
    referred_first_name: string | null;
    commission_amount: string;
    status: CommissionStatus;
    created_at: string;
    paid_at: string | null;
  }[];
}


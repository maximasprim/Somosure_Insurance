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
  coverage: Record<string, unknown>;
  exclusions: Record<string, unknown>;
  deductibles: Record<string, unknown>;
  payment_options: Record<string, unknown>;
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
  term_months: number;
  monthly_installment: string | null;
  is_mock: boolean;
}

export interface FinancingApplicationResult {
  id: string;
  reference: string;
  status: string;
  total_premium: string;
  deposit_amount: string;
  financed_amount: string;
  term_months: number;
  provider_reference: string | null;
  rejection_reason: string | null;
  created_at: string;
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

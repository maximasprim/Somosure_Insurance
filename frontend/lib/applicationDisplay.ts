// Display helpers for the admin application screen: friendly labels, which
// section a field belongs in, and readable values. Pure functions with no
// React in them, so they are easy to reason about and reuse.

import { CATEGORY_CONFIGS } from "@/lib/quoteFields";

/** Fields the quote form / document reader store, with the wording staff should see. */
const LABELS: Record<string, string> = {
  owner_name: "Full name",
  full_name: "Full name",
  owner_phone: "Phone",
  phone: "Phone",
  email: "Email",
  national_id_number: "National ID number",
  kra_pin: "KRA PIN",
  age: "Age",
  occupation: "Occupation",
  profession: "Profession",
  years_in_practice: "Years in practice",
  registration_number: "Registration number",
  chassis_number: "Chassis number",
  engine_number: "Engine number",
  make: "Make",
  model: "Model",
  year: "Year of manufacture",
  value: "Vehicle value",
  usage: "Usage",
  cover_type: "Cover type",
  vehicle_class: "Vehicle class",
  psv_type: "PSV type",
  tonnage: "Tonnage",
  seating_capacity: "Seating capacity",
  sum_insured: "Sum insured",
  cover_amount: "Cover amount",
  num_dependents: "Dependents",
  primary_age: "Primary member's age",
  hospital_tier: "Hospital tier",
  existing_conditions: "Existing conditions",
  destination_country: "Destination",
  trip_start_date: "Trip start",
  trip_end_date: "Trip end",
  num_travelers: "Travellers",
  trip_purpose: "Purpose of trip",
  property_use: "Property use",
  property_type: "Property type",
  insure_what: "Covering",
  security_level: "Security",
  term_years: "Term (years)",
  smoker: "Smoker",
  location: "Location",
};

/** Keys whose number is a Kenya-shilling amount. */
const MONEY_KEYS = new Set(["value", "sum_insured", "cover_amount"]);

/** Sections of the applicant card, in display order. */
export const APPLICANT_KEYS = [
  "owner_name",
  "full_name",
  "owner_phone",
  "phone",
  "email",
  "national_id_number",
  "kra_pin",
  "age",
  "occupation",
  "profession",
  "years_in_practice",
];
export const VEHICLE_KEYS = [
  "registration_number",
  "make",
  "model",
  "year",
  "value",
  "usage",
  "cover_type",
  "vehicle_class",
  "psv_type",
  "tonnage",
  "seating_capacity",
  "chassis_number",
  "engine_number",
];
/** Lists the customer ticked on the form - shown with the quote, not as applicant data. */
export const REQUESTED_LIST_KEYS = ["extensions", "cover_options"];

export function titleCase(text: string): string {
  return text.replace(/_/g, " ").replace(/\s+/g, " ").trim().replace(/\b\w/g, (c) => c.toUpperCase());
}

export function labelFor(key: string): string {
  return LABELS[key] ?? titleCase(key);
}

export function formatMoney(amount: string | number | null | undefined, currency = "KES"): string {
  if (amount === null || amount === undefined || amount === "") return "-";
  const n = Number(amount);
  if (Number.isNaN(n)) return String(amount);
  return `${currency} ${n.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" });
}

/** The wording the customer saw on the quote form for a ticked/selected value, if the form defines one. */
export function optionLabel(category: string | null | undefined, key: string, value: string): string | null {
  const field = category ? CATEGORY_CONFIGS[category]?.fields.find((f) => f.name === key) : undefined;
  return field?.options?.find((o) => o.value === value)?.label ?? null;
}

/** A readable version of one stored answer. */
export function formatAnswer(key: string, value: unknown, category?: string | null): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? value.map((v) => formatAnswer(key, v, category)).join(", ") : "-";
  if (typeof value === "object") return JSON.stringify(value);
  if (MONEY_KEYS.has(key)) return formatMoney(value as string | number);
  const text = String(value);
  const fromForm = optionLabel(category, key, text);
  if (fromForm) return fromForm;
  // Codes like "third_party_fire_theft" or "private" read better as words;
  // phone numbers, plates and free text are left exactly as typed.
  if (/^[a-z][a-z0-9_]*$/.test(text)) return titleCase(text);
  return text;
}

export function isInternalKey(key: string): boolean {
  return key.startsWith("_");
}

export interface DetailRow {
  key: string;
  label: string;
  value: string;
  /** Which uploaded document this value was read from, when it was read automatically. */
  readFrom?: string;
}

/** Picks the rows for one section, in the listed order. Missing/empty fields are skipped. */
export function rowsFor(
  details: Record<string, unknown>,
  keys: string[],
  extracted: Record<string, string> = {},
  category?: string | null
): DetailRow[] {
  const rows: DetailRow[] = [];
  const seenLabels = new Set<string>();
  for (const key of keys) {
    const raw = details[key];
    if (raw === null || raw === undefined || raw === "" || (Array.isArray(raw) && raw.length === 0)) continue;
    const label = labelFor(key);
    // owner_name and full_name both say "Full name" - show it once.
    if (seenLabels.has(label)) continue;
    seenLabels.add(label);
    rows.push({ key, label, value: formatAnswer(key, raw, category), readFrom: extracted[key] });
  }
  return rows;
}

/** Everything that is not applicant, vehicle or a requested list - the other risk answers. */
export function otherRows(details: Record<string, unknown>, category?: string | null): DetailRow[] {
  const claimed = new Set([...APPLICANT_KEYS, ...VEHICLE_KEYS, ...REQUESTED_LIST_KEYS]);
  const keys = Object.keys(details).filter((k) => !claimed.has(k) && !isInternalKey(k));
  return rowsFor(details, keys, {}, category);
}

export function extractedMarks(details: Record<string, unknown>): Record<string, string> {
  const marks = details["_extracted"];
  return marks && typeof marks === "object" && !Array.isArray(marks) ? (marks as Record<string, string>) : {};
}

const DOCUMENT_NAMES: Record<string, string> = {
  national_id: "national ID",
  kra_pin: "KRA PIN certificate",
  logbook: "logbook",
};

export function documentName(type: string): string {
  return DOCUMENT_NAMES[type] ?? titleCase(type).toLowerCase();
}

// --- quote & coverage shapes ----------------------------------------------

export interface ExtensionItem {
  code: string;
  label: string;
  amount: string;
  limit_label?: string | null;
}
export interface FreeBenefitItem {
  code: string;
  label: string;
  limit_label?: string | null;
  top_up_note?: string | null;
}
export interface ExcessItem {
  peril?: string;
  label: string;
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

/** Pulls the typed pieces out of a quote's loosely-shaped coverage/exclusions/deductibles. */
export function readQuoteSections(
  coverage: Record<string, unknown>,
  exclusions: Record<string, unknown>,
  deductibles: Record<string, unknown>
) {
  const extensions = asArray<ExtensionItem>(coverage.extensions).filter((e) => isObject(e));
  const freeBenefits = asArray<FreeBenefitItem>(coverage.free_benefits).filter((b) => isObject(b));
  const assumptions = asArray<string>(coverage.assumptions).filter((a) => typeof a === "string");

  const excesses: ExcessItem[] = asArray<ExcessItem>(deductibles.excesses).filter((e) => isObject(e));
  // Demo providers describe the excess as a single sentence instead of a list.
  if (typeof deductibles.excess === "string" && deductibles.excess) excesses.push({ label: deductibles.excess });

  const exclusionItems = asArray<string>(exclusions.items).filter((i) => typeof i === "string");

  // Anything else the provider returned that we have no special layout for.
  const known = new Set(["summary", "extensions", "free_benefits", "assumptions", "data_confidence_notice"]);
  const otherCoverage: DetailRow[] = Object.entries(coverage)
    .filter(([k, v]) => !known.has(k) && v !== null && v !== "" && !isObject(v))
    .map(([k, v]) => ({ key: k, label: labelFor(k), value: formatAnswer(k, v) }));

  return {
    summary: typeof coverage.summary === "string" ? coverage.summary : null,
    notice: typeof coverage.data_confidence_notice === "string" ? coverage.data_confidence_notice : null,
    extensions,
    freeBenefits,
    assumptions,
    excesses,
    exclusionItems,
    otherCoverage,
  };
}

export function sumExtensions(extensions: ExtensionItem[]): number {
  return extensions.reduce((total, e) => total + (Number(e.amount) || 0), 0);
}

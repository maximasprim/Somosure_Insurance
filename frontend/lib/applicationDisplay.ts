// Display helpers for the admin application screen: friendly labels, which
// section a field belongs in, and readable values. Pure functions with no
// React in them, so they are easy to reason about and reuse.

import { CATEGORY_CONFIGS } from "@/lib/quoteFields";

/** Fields the quote form / document reader store, with the wording staff should see. */
const LABELS: Record<string, string> = {
  owner_name: "Full name",
  full_name: "Full name",
  owner_phone: "Phone",
  owner_email: "Email",
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
  // Read from the valuation report (comprehensive motor cover).
  valuation_market_value: "Market value",
  valuation_forced_value: "Forced-sale value",
  valuation_windscreen_value: "Windscreen value (estimated)",
  valuation_radio_value: "Radio value (estimated)",
  valuation_reference: "Report reference",
  valuation_valuer: "Valued by",
  valuation_assessed_on: "Assessed on",
  valuation_inspected_at: "Inspected at",
  valuation_client: "Client named on report",
  valuation_registration_number: "Registration number",
  valuation_make_model: "Make & model",
  valuation_year: "Year of manufacture",
  valuation_body_type: "Body type",
  valuation_colour: "Colour",
  valuation_chassis_number: "Chassis number",
  valuation_engine_number: "Engine number",
  valuation_engine_cc: "Engine capacity",
  valuation_odometer_km: "Odometer",
  valuation_fuel_type: "Fuel",
  valuation_date_of_registration: "Date of registration",
  valuation_extras: "Extras fitted",
  valuation_general_condition: "General condition",
  valuation_accident_repairs: "Accident repairs on radiator / inner valances",
  valuation_chassis_frame_damage: "Chassis / crossmember damage",
  valuation_coachwork: "Coachwork notes",
  valuation_remarks: "Valuer's remarks",
  valuation_nb: "Valuer's note (NB)",
  valuation_remedy: "Remedy",
};

/** Keys whose number is a Kenya-shilling amount. */
const MONEY_KEYS = new Set([
  "value",
  "sum_insured",
  "cover_amount",
  "valuation_market_value",
  "valuation_forced_value",
  "valuation_windscreen_value",
  "valuation_radio_value",
]);
/** Stored as ISO dates (yyyy-mm-dd). */
const DATE_KEYS = new Set(["valuation_assessed_on", "valuation_date_of_registration"]);

/** Sections of the applicant card, in display order. */
export const APPLICANT_KEYS = [
  "owner_name",
  "full_name",
  "owner_phone",
  "phone",
  "owner_email",
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

// What was read off the valuation report, in the order staff should see it.
export const VALUATION_KEYS = [
  "valuation_market_value",
  "valuation_forced_value",
  "valuation_windscreen_value",
  "valuation_radio_value",
  "valuation_assessed_on",
  "valuation_valuer",
  "valuation_reference",
  "valuation_inspected_at",
  "valuation_client",
];
export const VALUATION_VEHICLE_KEYS = [
  "valuation_registration_number",
  "valuation_make_model",
  "valuation_year",
  "valuation_body_type",
  "valuation_colour",
  "valuation_chassis_number",
  "valuation_engine_number",
  "valuation_engine_cc",
  "valuation_odometer_km",
  "valuation_fuel_type",
  "valuation_date_of_registration",
  "valuation_extras",
];
export const VALUATION_CONDITION_KEYS = [
  "valuation_general_condition",
  "valuation_accident_repairs",
  "valuation_chassis_frame_damage",
  "valuation_coachwork",
  "valuation_remarks",
  "valuation_nb",
  "valuation_remedy",
];
export const ALL_VALUATION_KEYS = [...VALUATION_KEYS, ...VALUATION_VEHICLE_KEYS, ...VALUATION_CONDITION_KEYS];

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
  if (DATE_KEYS.has(key)) return formatDate(String(value));
  if (key === "valuation_odometer_km" && !Number.isNaN(Number(value))) return `${Number(value).toLocaleString("en-KE")} km`;
  if (key === "valuation_engine_cc" && !Number.isNaN(Number(value))) return `${Number(value).toLocaleString("en-KE")} cc`;
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
  /** "warn" marks a value staff should look at twice (shown in amber). */
  tone?: "warn";
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
  const claimed = new Set([...APPLICANT_KEYS, ...VEHICLE_KEYS, ...REQUESTED_LIST_KEYS, ...ALL_VALUATION_KEYS]);
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
  valuation_report: "valuation report",
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
  const known = new Set(["summary", "extensions", "optional_extensions", "free_benefits", "assumptions", "data_confidence_notice"]);
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

// --- comprehensive cover & the valuation report ----------------------------

/** True when the quote was priced as comprehensive cover. A rate-card quote records what it was
 *  actually priced as (a car too old for comprehensive is quoted third-party even if comprehensive
 *  was asked for); otherwise what the customer chose on the form is used. */
export function isComprehensiveCover(
  providerMetadata: Record<string, unknown> | undefined | null,
  details: Record<string, unknown>
): boolean {
  const priced = providerMetadata?.["cover_type"];
  const chosen = typeof priced === "string" && priced ? priced : details["cover_type"];
  return typeof chosen === "string" && chosen.trim().toLowerCase() === "comprehensive";
}

/** A declared value more than this far from the valuation's market value is flagged. A display
 *  hint for the reviewer only - it never blocks or changes anything. */
export const VALUE_TOLERANCE = 0.1;

export interface ValuationCheck {
  level: "warn" | "info";
  text: string;
}

const plain = (v: unknown) => String(v ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");

/**
 * Compares what was read from the valuation report with what the customer declared and what the
 * logbook says, so a reviewer sees disagreements without hunting for them. Only compares two values
 * that are both present.
 */
export function valuationChecks(
  details: Record<string, unknown>,
  declared: { value?: unknown; registration?: unknown; chassis?: unknown; engine?: unknown }
): ValuationCheck[] {
  const checks: ValuationCheck[] = [];
  const market = Number(details["valuation_market_value"]);
  const declaredValue = Number(declared.value);
  if (market > 0 && declaredValue > 0) {
    const diff = (declaredValue - market) / market;
    const pct = Math.round(Math.abs(diff) * 100);
    if (Math.abs(diff) > VALUE_TOLERANCE) {
      checks.push({
        level: "warn",
        text: `Customer declared ${formatMoney(declaredValue)}; the valuation's market value is ${formatMoney(market)} (${pct}% ${diff > 0 ? "higher" : "lower"}).`,
      });
    } else {
      checks.push({
        level: "info",
        text: `Declared value ${formatMoney(declaredValue)} is within ${Math.round(VALUE_TOLERANCE * 100)}% of the valuation's market value.`,
      });
    }
  }
  const pairs: [string, string, unknown][] = [
    ["valuation_registration_number", "registration number", declared.registration],
    ["valuation_chassis_number", "chassis number", declared.chassis],
    ["valuation_engine_number", "engine number", declared.engine],
  ];
  for (const [key, label, other] of pairs) {
    const onReport = plain(details[key]);
    const elsewhere = plain(other);
    if (onReport && elsewhere && onReport !== elsewhere) {
      checks.push({
        level: "warn",
        text: `The ${label} on the valuation (${String(details[key])}) is not the one on the application (${String(other)}).`,
      });
    }
  }
  return checks;
}

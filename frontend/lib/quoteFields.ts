export type FieldType = "text" | "number" | "date" | "select" | "tel";

export interface FieldDef {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: { value: string; label: string }[];
  placeholder?: string;
}

export interface CategoryConfig {
  category: string;
  title: string;
  fields: FieldDef[];
}

// Kept intentionally short per category - enough to price a rough quote,
// not a full underwriting questionnaire (spec §53: progressive
// disclosure, ask only what's needed up front).
export const CATEGORY_CONFIGS: Record<string, CategoryConfig> = {
  medical: {
    category: "medical",
    title: "Medical insurance quote",
    fields: [
      { name: "cover_type", label: "Cover type", type: "select", required: true, options: [
        { value: "individual", label: "Individual" },
        { value: "family", label: "Family" },
      ] },
      { name: "num_dependents", label: "Number of dependents", type: "number", placeholder: "0" },
      { name: "primary_age", label: "Primary member's age", type: "number", required: true },
      { name: "hospital_tier", label: "Preferred hospital tier", type: "select", required: true, options: [
        { value: "basic", label: "Basic (Level 4 hospitals)" },
        { value: "standard", label: "Standard (Level 5 hospitals)" },
        { value: "premium", label: "Premium (Level 6 / private)" },
      ] },
      { name: "existing_conditions", label: "Any existing medical conditions?", type: "select", options: [
        { value: "no", label: "No" },
        { value: "yes", label: "Yes" },
      ] },
      { name: "full_name", label: "Your full name", type: "text", required: true },
      { name: "phone", label: "Your phone number", type: "tel", required: true, placeholder: "07XX XXX XXX" },
    ],
  },
  life: {
    category: "life",
    title: "Life insurance quote",
    fields: [
      { name: "cover_amount", label: "Cover amount (KES)", type: "number", required: true, placeholder: "1000000" },
      { name: "term_years", label: "Term (years)", type: "number", required: true, placeholder: "10" },
      { name: "age", label: "Your age", type: "number", required: true },
      { name: "smoker", label: "Do you smoke?", type: "select", required: true, options: [
        { value: "no", label: "No" },
        { value: "yes", label: "Yes" },
      ] },
      { name: "full_name", label: "Your full name", type: "text", required: true },
      { name: "phone", label: "Your phone number", type: "tel", required: true, placeholder: "07XX XXX XXX" },
    ],
  },
  travel: {
    category: "travel",
    title: "Travel insurance quote",
    fields: [
      { name: "destination_country", label: "Destination country", type: "text", required: true },
      { name: "trip_start_date", label: "Trip start date", type: "date", required: true },
      { name: "trip_end_date", label: "Trip end date", type: "date", required: true },
      { name: "num_travelers", label: "Number of travelers", type: "number", required: true, placeholder: "1" },
      { name: "trip_purpose", label: "Purpose of trip", type: "select", options: [
        { value: "leisure", label: "Leisure" },
        { value: "business", label: "Business" },
        { value: "study", label: "Study" },
      ] },
      { name: "full_name", label: "Your full name", type: "text", required: true },
      { name: "phone", label: "Your phone number", type: "tel", required: true, placeholder: "07XX XXX XXX" },
    ],
  },
  home: {
    category: "home",
    title: "Home insurance quote",
    fields: [
      { name: "property_type", label: "Property type", type: "select", required: true, options: [
        { value: "apartment", label: "Apartment" },
        { value: "house", label: "Standalone house" },
      ] },
      { name: "property_value", label: "Estimated property value (KES)", type: "number", required: true },
      { name: "location", label: "Location (area/town)", type: "text", required: true },
      { name: "num_bedrooms", label: "Number of bedrooms", type: "number" },
      { name: "has_security", label: "Gated/secured compound?", type: "select", options: [
        { value: "yes", label: "Yes" },
        { value: "no", label: "No" },
      ] },
      { name: "full_name", label: "Your full name", type: "text", required: true },
      { name: "phone", label: "Your phone number", type: "tel", required: true, placeholder: "07XX XXX XXX" },
    ],
  },
  business: {
    category: "business",
    title: "Business insurance quote",
    fields: [
      { name: "business_type", label: "Nature of business", type: "text", required: true, placeholder: "e.g. retail shop, restaurant" },
      { name: "cover_type", label: "Cover type", type: "select", required: true, options: [
        { value: "property", label: "Property" },
        { value: "liability", label: "Liability" },
        { value: "combined", label: "Combined" },
      ] },
      { name: "annual_revenue", label: "Estimated annual revenue (KES)", type: "number" },
      { name: "num_employees", label: "Number of employees", type: "number" },
      { name: "property_value", label: "Property/asset value (KES)", type: "number" },
      { name: "full_name", label: "Your full name", type: "text", required: true },
      { name: "phone", label: "Your phone number", type: "tel", required: true, placeholder: "07XX XXX XXX" },
    ],
  },
  personal_accident: {
    category: "personal_accident",
    title: "Personal accident insurance quote",
    fields: [
      { name: "cover_amount", label: "Cover amount (KES)", type: "number", required: true, placeholder: "500000" },
      { name: "age", label: "Your age", type: "number", required: true },
      { name: "occupation", label: "Occupation", type: "text", required: true },
      { name: "full_name", label: "Your full name", type: "text", required: true },
      { name: "phone", label: "Your phone number", type: "tel", required: true, placeholder: "07XX XXX XXX" },
    ],
  },
  professional_indemnity: {
    category: "professional_indemnity",
    title: "Professional indemnity insurance quote",
    fields: [
      { name: "profession", label: "Profession", type: "text", required: true, placeholder: "e.g. architect, consultant, lawyer" },
      { name: "cover_amount", label: "Cover amount (KES)", type: "number", required: true, placeholder: "5000000" },
      { name: "years_in_practice", label: "Years in practice", type: "number" },
      { name: "annual_fee_income", label: "Estimated annual fee income (KES)", type: "number" },
      { name: "prior_claims", label: "Any claims in the last 5 years?", type: "select", options: [
        { value: "no", label: "No" },
        { value: "yes", label: "Yes" },
      ] },
      { name: "full_name", label: "Your full name", type: "text", required: true },
      { name: "phone", label: "Your phone number", type: "tel", required: true, placeholder: "07XX XXX XXX" },
    ],
  },
  wiba: {
    category: "wiba",
    title: "Work Injury Benefits (WIBA) insurance quote",
    fields: [
      { name: "business_type", label: "Nature of business", type: "text", required: true, placeholder: "e.g. construction, manufacturing, office" },
      { name: "num_employees", label: "Number of employees", type: "number", required: true },
      { name: "annual_payroll", label: "Estimated annual payroll (KES)", type: "number", required: true },
      { name: "work_risk_level", label: "Nature of work", type: "select", required: true, options: [
        { value: "low", label: "Low risk (office-based)" },
        { value: "medium", label: "Medium risk (retail, light industry)" },
        { value: "high", label: "High risk (construction, manufacturing)" },
      ] },
      { name: "full_name", label: "Your full name", type: "text", required: true },
      { name: "phone", label: "Your phone number", type: "tel", required: true, placeholder: "07XX XXX XXX" },
    ],
  },
};

export type FieldType = "text" | "number" | "date" | "select" | "tel" | "checkboxes";

export interface FieldOption {
  value: string;
  label: string;
  // Short explanation shown under a checkbox option.
  hint?: string;
  // Options with the same group are listed together under that heading.
  group?: string;
}

export interface FieldDef {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: FieldOption[];
  placeholder?: string;
  // Help text under the field's label.
  description?: string;
  // For "checkboxes": the values ticked to begin with.
  defaultValue?: string[];
}

export interface CategoryConfig {
  category: string;
  title: string;
  fields: FieldDef[];
  // A product announced but not yet quotable online: the page shows "coming
  // soon" and the agent hand-off instead of a form. To launch it, remove this
  // flag, add its fields, and remove it from COMING_SOON_ALWAYS in the
  // backend (backend/app/services/product_catalog.py).
  comingSoon?: boolean;
  // What the coming-soon screen says the product is planned to cover.
  highlights?: string[];
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
  property: {
    category: "property",
    title: "Property insurance quote",
    fields: [
      { name: "property_use", label: "What are you insuring?", type: "select", required: true, options: [
        { value: "home", label: "A home I live in" },
        { value: "rental", label: "A rental property I own (landlord)" },
        { value: "business", label: "My business premises" },
      ] },
      { name: "property_type", label: "Type of property", type: "select", required: true, options: [
        { value: "apartment", label: "Apartment / flat" },
        { value: "house", label: "Standalone house / maisonette" },
        { value: "shop_office", label: "Shop or office" },
        { value: "warehouse_factory", label: "Warehouse or factory" },
        { value: "other", label: "Other" },
      ] },
      { name: "insure_what", label: "What should be covered?", type: "select", required: true, options: [
        { value: "building", label: "The building / structure" },
        { value: "contents", label: "Contents or stock" },
        { value: "both", label: "Both building and contents" },
      ] },
      { name: "sum_insured", label: "Total value to insure (KES)", type: "number", required: true, placeholder: "5000000" },
      { name: "location", label: "Location (area/town)", type: "text", required: true },
      { name: "security_level", label: "Security in place", type: "select", options: [
        { value: "none", label: "None" },
        { value: "guard", label: "Gated compound or guard" },
        { value: "alarm_cctv", label: "Alarm or CCTV" },
        { value: "both", label: "Guard and alarm / CCTV" },
      ] },
      {
        name: "cover_options",
        label: "What do you want to be covered against?",
        description: "Tick everything you want in your quote - you can change it any time before you buy.",
        type: "checkboxes",
        required: true,
        defaultValue: ["fire", "theft_burglary"],
        options: [
          { value: "fire", group: "Main cover", label: "Fire & lightning", hint: "Fire, lightning, explosion and related damage." },
          { value: "theft_burglary", group: "Main cover", label: "Theft & burglary", hint: "Break-ins, forced entry and theft of insured items." },
          { value: "natural_perils", group: "Other options", label: "Flood, storm & other natural perils", hint: "Damage from flooding, storms and similar events." },
          { value: "riot_malicious", group: "Other options", label: "Riot, strike & malicious damage", hint: "Damage from civil unrest or deliberate acts." },
          { value: "accidental_damage", group: "Other options", label: "Accidental damage", hint: "Sudden, unexpected damage to the property." },
          { value: "all_risks", group: "Other options", label: "All risks (portable valuables)", hint: "Jewellery, cameras and other items you carry about." },
          { value: "electronic_equipment", group: "Other options", label: "Electronic equipment", hint: "Computers, TVs and office equipment." },
          { value: "money", group: "Other options", label: "Money in safe or in transit", hint: "Cash kept on the premises or being banked." },
          { value: "glass", group: "Other options", label: "Glass breakage", hint: "Windows, doors and display glass." },
          { value: "public_liability", group: "Other options", label: "Public liability", hint: "If someone is hurt or their property damaged because of yours." },
          { value: "business_interruption", group: "Other options", label: "Business interruption", hint: "Lost income while you can't trade after a covered loss." },
          { value: "machinery_breakdown", group: "Other options", label: "Machinery breakdown", hint: "Equipment that stops working because of a fault." },
        ],
      },
      { name: "full_name", label: "Your full name", type: "text", required: true },
      { name: "phone", label: "Your phone number", type: "tel", required: true, placeholder: "07XX XXX XXX" },
    ],
  },
  cargo: {
    category: "cargo",
    title: "Cargo insurance quote",
    comingSoon: true,
    highlights: [
      "Local cargo - goods moving by road or rail within Kenya and the region",
      "Marine cargo - imports and exports by sea and air",
      "Single trips or an annual policy for regular shippers",
    ],
    fields: [],
  },
  hull: {
    category: "hull",
    title: "Hull insurance quote",
    comingSoon: true,
    highlights: [
      "Boats, dhows, ferries and other vessels",
      "Damage to the hull, machinery and equipment",
      "Cover for vessels in port and at sea",
    ],
    fields: [],
  },
  cybersecurity: {
    category: "cybersecurity",
    title: "Cybersecurity insurance quote",
    comingSoon: true,
    highlights: [
      "Data breaches and the cost of responding to them",
      "Ransomware and cyber extortion",
      "Income lost while your systems are down",
    ],
    fields: [],
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

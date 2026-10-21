import { Card } from "@/components/ui/Card";
import { ValuationSection } from "@/components/admin/ValuationSection";
import {
  ALL_VALUATION_KEYS,
  APPLICANT_KEYS,
  VEHICLE_KEYS,
  documentName,
  extractedMarks,
  otherRows,
  rowsFor,
  valuationChecks,
  type DetailRow,
} from "@/lib/applicationDisplay";
import type { ApplicationCustomer, ApplicationVehicle } from "@/lib/types";

// ID number and KRA PIN are read from the uploaded documents, so until then
// they are shown as "not read yet" rather than silently missing.
const READ_FROM_DOCUMENTS = ["national_id_number", "kra_pin"];

function Field({ row }: { row: DetailRow }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-neutral-border/60 py-2.5">
      <dt className="shrink-0 text-sm text-ink-soft">{row.label}</dt>
      <dd
        className={`min-w-0 break-words text-right text-sm font-medium ${row.tone === "warn" ? "text-amber-700" : "text-ink"}`}
      >
        {row.value}
        {row.readFrom && (
          <span className="ml-2 inline-block rounded-full bg-brand-tint px-2 py-0.5 align-middle text-[11px] font-normal text-ink-soft">
            read from {documentName(row.readFrom)}
          </span>
        )}
      </dd>
    </div>
  );
}

function PendingField({ label }: { label: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-neutral-border/60 py-2.5">
      <dt className="shrink-0 text-sm text-ink-soft">{label}</dt>
      <dd className="text-right text-sm italic text-ink-soft/70">Not read yet</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6 first:mt-0">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink-soft">{title}</h3>
      <dl className="mt-1 grid grid-cols-1 gap-x-10 md:grid-cols-2">{children}</dl>
    </section>
  );
}

export function ApplicantDetailsCard({
  details,
  customer,
  category,
  hasVehicleRecord,
  isComprehensive = false,
  vehicleRecord = null,
}: {
  details: Record<string, unknown>;
  customer: ApplicationCustomer;
  category?: string | null;
  /** When a Vehicle record exists the page already shows it, so don't repeat the vehicle here. */
  hasVehicleRecord: boolean;
  /** Comprehensive motor cover: the valuation report is required, so show its section even before it is read. */
  isComprehensive?: boolean;
  /** The vehicle record, when there is one - used to compare against the valuation report. */
  vehicleRecord?: ApplicationVehicle | null;
}) {
  const marks = extractedMarks(details);

  // The customer record may already hold an ID number / KRA PIN (typed on
  // their profile, or read from an earlier application).
  const merged: Record<string, unknown> = { ...details };
  if (!merged.national_id_number && customer.id_number) merged.national_id_number = customer.id_number;
  if (!merged.kra_pin && customer.kra_pin) merged.kra_pin = customer.kra_pin;
  if (!merged.owner_name && !merged.full_name) merged.full_name = customer.full_name;
  if (!merged.owner_phone && !merged.phone) merged.phone = customer.phone;
  if (!merged.email && customer.email) merged.email = customer.email;

  const applicant = rowsFor(merged, APPLICANT_KEYS, marks, category);
  const pending = READ_FROM_DOCUMENTS.filter((key) => !applicant.some((r) => r.key === key));
  const vehicle = hasVehicleRecord ? [] : rowsFor(merged, VEHICLE_KEYS, marks, category);
  const other = otherRows(details, category);

  // Valuation report (comprehensive motor cover). Shown when the cover needs one or when one has
  // been read; values the reader did not find stay visible as "not read yet" rather than missing.
  const hasValuation = ALL_VALUATION_KEYS.some((k) => details[k]);
  const showValuation = hasValuation || (isComprehensive && category === "motor");
  const checks = hasValuation
    ? valuationChecks(details, {
        value: vehicleRecord?.value ?? details["value"],
        registration: vehicleRecord?.registration_number ?? details["registration_number"],
        chassis: vehicleRecord?.chassis_number ?? details["chassis_number"],
        engine: vehicleRecord?.engine_number ?? details["engine_number"],
      })
    : [];
  const fromForm = details["_prefilled_from"] === "quote_form";

  return (
    <Card>
      <h2 className="font-semibold">Applicant details</h2>
      <p className="mt-1 text-xs text-ink-soft">
        {fromForm ? "Copied from the customer's quote form. " : ""}
        ID number, KRA PIN{showValuation ? ", the valuation report" : ""} and logbook numbers are read automatically from the
        uploaded documents.
      </p>

      <div className="mt-5">
        <Section title="Applicant">
          {applicant.map((row) => (
            <Field key={row.key} row={row} />
          ))}
          {pending.map((key) => (
            <PendingField key={key} label={key === "kra_pin" ? "KRA PIN" : "National ID number"} />
          ))}
        </Section>

        {vehicle.length > 0 && (
          <Section title="Vehicle">
            {vehicle.map((row) => (
              <Field key={row.key} row={row} />
            ))}
          </Section>
        )}

        {showValuation && <ValuationSection details={details} checks={checks} />}

        {other.length > 0 && (
          <Section title="Risk details">
            {other.map((row) => (
              <Field key={row.key} row={row} />
            ))}
          </Section>
        )}
      </div>
    </Card>
  );
}

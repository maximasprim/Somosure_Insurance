import {
  VALUATION_CONDITION_KEYS,
  VALUATION_KEYS,
  VALUATION_VEHICLE_KEYS,
  formatAnswer,
  labelFor,
  type ValuationCheck,
} from "@/lib/applicationDisplay";

/**
 * The "Valuation report" part of the applicant details card (comprehensive motor cover).
 *
 * Laid out for reading rather than as one long list of rows: the figures first, who/when under
 * them, then anything that disagrees with the application, the vehicle as inspected, and the
 * condition. Every value that was read from the report is shown; one tag in the header says where
 * they all came from (rather than repeating it on every line).
 */

const has = (details: Record<string, unknown>, key: string) => {
  const v = details[key];
  return v !== null && v !== undefined && v !== "";
};
const show = (details: Record<string, unknown>, key: string) => formatAnswer(key, details[key], "motor");

/** Valuers type notes in capitals; show them as ordinary sentences. The stored text is not changed. */
function soften(text: string): string {
  if (text !== text.toUpperCase() || !/[A-Z]/.test(text)) return text;
  return text.toLowerCase().replace(/(^|[.!?]\s+)([a-z])/g, (_, lead: string, c: string) => lead + c.toUpperCase());
}

/** "Abs, Booster, Power Steering , Power Steering,power Windows" -> tidy, de-duplicated chips. */
function chips(list: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of list.split(",")) {
    const item = part.trim();
    const key = item.toLowerCase();
    if (!item || seen.has(key)) continue;
    seen.add(key);
    // Short codes (ABS, CDL) are abbreviations, not words.
    out.push(item.length <= 3 ? item.toUpperCase() : item.charAt(0).toUpperCase() + item.slice(1));
  }
  return out;
}

function Tile({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) {
  return (
    <div
      className={`rounded-control border px-3.5 py-3 ${
        emphasis ? "col-span-2 border-brand-deep/40 bg-brand-tint md:col-span-1" : "border-neutral-border"
      }`}
    >
      <dt className="text-[11px] font-medium uppercase tracking-wide text-ink-soft">{label}</dt>
      <dd className={`mt-1 break-words font-semibold text-ink ${emphasis ? "text-xl" : "text-base"}`}>{value}</dd>
    </div>
  );
}

function SubHeading({ children }: { children: React.ReactNode }) {
  return <h4 className="text-[11px] font-semibold uppercase tracking-wider text-ink-soft">{children}</h4>;
}

export function ValuationSection({
  details,
  checks,
}: {
  details: Record<string, unknown>;
  checks: ValuationCheck[];
}) {
  const read = has(details, "valuation_market_value");

  const figures = ["valuation_market_value", "valuation_forced_value", "valuation_windscreen_value", "valuation_radio_value"];
  const meta = VALUATION_KEYS.filter((k) => !figures.includes(k) && has(details, k));
  const vehicleKeys = VALUATION_VEHICLE_KEYS.filter((k) => k !== "valuation_extras" && has(details, k));
  const extras = has(details, "valuation_extras") ? chips(String(details["valuation_extras"])) : [];
  const status = ["valuation_general_condition", "valuation_accident_repairs", "valuation_chassis_frame_damage"].filter((k) =>
    has(details, k)
  );
  const notes = VALUATION_CONDITION_KEYS.filter((k) => ["valuation_coachwork", "valuation_remarks", "valuation_nb", "valuation_remedy"].includes(k) && has(details, k));

  return (
    <section className="mt-8 border-t border-neutral-border/60 pt-6" aria-label="Valuation report">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink-soft">Valuation report</h3>
        {read && (
          <span className="rounded-full bg-brand-tint px-2.5 py-0.5 text-[11px] text-ink-soft">Read from the uploaded report</span>
        )}
      </div>

      {!read ? (
        <p className="mt-3 rounded-control border border-dashed border-neutral-border px-4 py-3 text-sm italic text-ink-soft/80">
          Market value: not read yet. Upload the valuation report, or use &ldquo;Re-read documents&rdquo; below once it is uploaded.
        </p>
      ) : (
        <dl className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          {figures
            .filter((k) => has(details, k))
            .map((k) => (
              <Tile key={k} label={labelFor(k)} value={show(details, k)} emphasis={k === "valuation_market_value"} />
            ))}
        </dl>
      )}

      {meta.length > 0 && (
        <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1.5 text-xs">
          {meta.map((k) => (
            <div key={k} className="flex gap-1.5">
              <dt className="text-ink-soft">{labelFor(k)}</dt>
              <dd className="font-medium text-ink">{show(details, k)}</dd>
            </div>
          ))}
        </dl>
      )}

      {checks.length > 0 && (
        <ul className="mt-4 flex flex-col gap-1.5">
          {checks.map((check) => (
            <li
              key={check.text}
              className={`rounded-control border px-3 py-2 text-xs ${
                check.level === "warn" ? "border-amber-200 bg-amber-50 text-amber-800" : "border-neutral-border bg-neutral text-ink-soft"
              }`}
            >
              {check.text}
            </li>
          ))}
        </ul>
      )}

      {(vehicleKeys.length > 0 || extras.length > 0) && (
        <div className="mt-6">
          <SubHeading>Vehicle as inspected</SubHeading>
          {vehicleKeys.length > 0 && (
            <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-3">
              {vehicleKeys.map((k) => (
                <div key={k} className="min-w-0">
                  <dt className="text-xs text-ink-soft">{labelFor(k)}</dt>
                  <dd className="mt-0.5 break-words text-sm font-medium text-ink">{show(details, k)}</dd>
                </div>
              ))}
            </dl>
          )}
          {extras.length > 0 && (
            <div className="mt-4">
              <p className="text-xs text-ink-soft">{labelFor("valuation_extras")}</p>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {extras.map((item) => (
                  <li key={item} className="rounded-full bg-neutral px-2.5 py-1 text-xs text-ink">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {(status.length > 0 || notes.length > 0) && (
        <div className="mt-6">
          <SubHeading>Condition at inspection</SubHeading>
          {status.length > 0 && (
            <dl className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
              {status.map((k) => {
                // Earlier accident repairs or frame damage are what an underwriter looks for first.
                const warn = k !== "valuation_general_condition" && /^yes$/i.test(String(details[k]));
                return (
                  <div
                    key={k}
                    className={`rounded-control border px-3.5 py-3 ${warn ? "border-amber-200 bg-amber-50" : "border-neutral-border"}`}
                  >
                    <dt className="text-xs text-ink-soft">{labelFor(k)}</dt>
                    <dd className={`mt-1 text-sm font-semibold ${warn ? "text-amber-800" : "text-ink"}`}>{show(details, k)}</dd>
                  </div>
                );
              })}
            </dl>
          )}
          {notes.length > 0 && (
            <dl className="mt-4 flex flex-col gap-3">
              {notes.map((k) => (
                <div key={k}>
                  <dt className="text-xs text-ink-soft">{labelFor(k)}</dt>
                  <dd className="mt-0.5 text-sm leading-relaxed text-ink">{soften(String(details[k]))}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}
    </section>
  );
}

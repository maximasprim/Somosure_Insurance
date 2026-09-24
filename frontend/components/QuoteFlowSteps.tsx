import clsx from "clsx";

const STEPS = ["Details", "Compare", "Documents", "Confirmation"];

export function QuoteFlowSteps({ current }: { current: number }) {
  return (
    <ol className="mb-8 flex items-center gap-1 overflow-x-auto text-sm sm:gap-2">
      {STEPS.map((label, i) => (
        <li key={label} className="flex shrink-0 items-center gap-1 sm:gap-2">
          <span
            className={clsx(
              "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
              i === current
                ? "bg-brand text-ink"
                : i < current
                ? "bg-status-success/15 text-status-success"
                : "bg-neutral text-ink-soft"
            )}
          >
            {i + 1}
          </span>
          <span
            className={clsx(
              "whitespace-nowrap",
              i === current ? "inline font-semibold text-ink" : "hidden text-ink-soft sm:inline"
            )}
          >
            {label}
          </span>
          {i < STEPS.length - 1 && <span className="mx-0.5 h-px w-3 shrink-0 bg-neutral-border sm:mx-1 sm:w-6" />}
        </li>
      ))}
    </ol>
  );
}

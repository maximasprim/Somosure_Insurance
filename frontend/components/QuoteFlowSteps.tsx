import clsx from "clsx";

const STEPS = ["Details", "Compare", "Documents", "Confirmation"];

export function QuoteFlowSteps({ current }: { current: number }) {
  return (
    <ol className="mb-8 flex items-center gap-2 text-sm">
      {STEPS.map((label, i) => (
        <li key={label} className="flex items-center gap-2">
          <span
            className={clsx(
              "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold",
              i === current
                ? "bg-brand text-ink"
                : i < current
                ? "bg-status-success/15 text-status-success"
                : "bg-neutral text-ink-soft"
            )}
          >
            {i + 1}
          </span>
          <span className={clsx(i === current ? "font-semibold text-ink" : "text-ink-soft")}>{label}</span>
          {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-neutral-border" />}
        </li>
      ))}
    </ol>
  );
}

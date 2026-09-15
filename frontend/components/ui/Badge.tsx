import { HTMLAttributes } from "react";
import clsx from "clsx";

type Tone = "neutral" | "success" | "error" | "info" | "brand";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

const toneClasses: Record<Tone, string> = {
  neutral: "bg-neutral text-ink-soft",
  success: "bg-status-success/10 text-status-success",
  error: "bg-status-error/10 text-status-error",
  info: "bg-status-info/10 text-status-info",
  brand: "bg-brand-tint text-ink",
};

export function Badge({ tone = "neutral", className, ...props }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium",
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}

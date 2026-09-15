import { InputHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, id, className, ...props }, ref) => (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={id}
        className={clsx(
          "rounded-control border bg-white px-4 py-2.5 text-sm text-ink placeholder:text-ink-soft/60",
          "focus:outline-none focus:ring-2 focus:ring-brand-deep/40 focus:border-brand-deep",
          error ? "border-status-error" : "border-neutral-border",
          className
        )}
        aria-invalid={!!error}
        {...props}
      />
      {error && <p className="text-xs text-status-error">{error}</p>}
    </div>
  )
);
Input.displayName = "Input";

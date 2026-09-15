import { HTMLAttributes } from "react";
import clsx from "clsx";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={clsx(
        "rounded-card border border-neutral-border bg-white shadow-card p-6",
        className
      )}
      {...props}
    />
  );
}

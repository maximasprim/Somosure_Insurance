"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { CategoryConfig } from "@/lib/quoteFields";

export function DynamicQuoteForm({
  config,
  onSubmit,
  submitting,
}: {
  config: CategoryConfig;
  onSubmit: (values: Record<string, string>) => void;
  submitting: boolean;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  function handleChange(name: string, value: string) {
    setValues((v) => ({ ...v, [name]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const nextErrors: Record<string, string> = {};
    for (const field of config.fields) {
      if (field.required && !values[field.name]?.trim()) {
        nextErrors[field.name] = `${field.label} is required`;
      }
    }
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }
    setErrors({});
    onSubmit(values);
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-5 sm:grid-cols-2">
      {config.fields.map((field) => {
        if (field.type === "select") {
          return (
            <div key={field.name} className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-ink">{field.label}</label>
              <select
                value={values[field.name] ?? ""}
                onChange={(e) => handleChange(field.name, e.target.value)}
                className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm"
              >
                <option value="">Select…</option>
                {field.options?.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              {errors[field.name] && <p className="text-xs text-status-error">{errors[field.name]}</p>}
            </div>
          );
        }
        return (
          <Input
            key={field.name}
            label={field.label}
            type={field.type === "tel" ? "tel" : field.type}
            placeholder={field.placeholder}
            value={values[field.name] ?? ""}
            onChange={(e) => handleChange(field.name, e.target.value)}
            error={errors[field.name]}
          />
        );
      })}

      <div className="sm:col-span-2">
        <Button type="submit" size="lg" disabled={submitting} className="w-full sm:w-auto">
          {submitting ? "Getting quotes…" : "Compare quotes"}
        </Button>
      </div>
    </form>
  );
}

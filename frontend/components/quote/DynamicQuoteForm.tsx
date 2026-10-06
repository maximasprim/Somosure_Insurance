"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { CategoryConfig, FieldDef } from "@/lib/quoteFields";

export type QuoteAnswers = Record<string, string | string[]>;

function initialValues(config: CategoryConfig): QuoteAnswers {
  const values: QuoteAnswers = {};
  for (const field of config.fields) {
    if (field.type === "checkboxes") values[field.name] = [...(field.defaultValue ?? [])];
  }
  return values;
}

function isEmpty(field: FieldDef, value: string | string[] | undefined): boolean {
  if (field.type === "checkboxes") return !Array.isArray(value) || value.length === 0;
  return typeof value !== "string" || !value.trim();
}

export function DynamicQuoteForm({
  config,
  onSubmit,
  submitting,
}: {
  config: CategoryConfig;
  onSubmit: (values: QuoteAnswers) => void;
  submitting: boolean;
}) {
  const [values, setValues] = useState<QuoteAnswers>(() => initialValues(config));
  const [errors, setErrors] = useState<Record<string, string>>({});

  function handleChange(name: string, value: string) {
    setValues((v) => ({ ...v, [name]: value }));
  }

  function toggle(name: string, option: string) {
    setValues((v) => {
      const current = Array.isArray(v[name]) ? (v[name] as string[]) : [];
      return { ...v, [name]: current.includes(option) ? current.filter((o) => o !== option) : [...current, option] };
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const nextErrors: Record<string, string> = {};
    for (const field of config.fields) {
      if (field.required && isEmpty(field, values[field.name])) {
        nextErrors[field.name] =
          field.type === "checkboxes" ? "Please tick at least one option" : `${field.label} is required`;
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
        if (field.type === "checkboxes") {
          const chosen = Array.isArray(values[field.name]) ? (values[field.name] as string[]) : [];
          const groups: { title: string; options: NonNullable<FieldDef["options"]> }[] = [];
          for (const opt of field.options ?? []) {
            const title = opt.group ?? "";
            const existing = groups.find((g) => g.title === title);
            if (existing) existing.options.push(opt);
            else groups.push({ title, options: [opt] });
          }
          return (
            <fieldset key={field.name} className="flex flex-col gap-3 sm:col-span-2">
              <legend className="text-sm font-medium text-ink">{field.label}</legend>
              {field.description && <p className="-mt-1 text-xs text-ink-soft">{field.description}</p>}
              {groups.map((group) => (
                <div key={group.title} className="flex flex-col gap-2">
                  {group.title && <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">{group.title}</p>}
                  <div className="grid gap-2 sm:grid-cols-2">
                    {group.options.map((opt) => {
                      const checked = chosen.includes(opt.value);
                      return (
                        <label
                          key={opt.value}
                          className={`flex cursor-pointer items-start gap-3 rounded-control border px-4 py-3 text-sm transition-colors ${
                            checked ? "border-brand-deep bg-brand-tint/40" : "border-neutral-border hover:border-brand-deep/50"
                          }`}
                        >
                          <input
                            type="checkbox"
                            className="mt-0.5 h-4 w-4 shrink-0"
                            checked={checked}
                            onChange={() => toggle(field.name, opt.value)}
                          />
                          <span>
                            <span className="block font-medium text-ink">{opt.label}</span>
                            {opt.hint && <span className="mt-0.5 block text-xs text-ink-soft">{opt.hint}</span>}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
              {errors[field.name] && <p className="text-xs text-status-error">{errors[field.name]}</p>}
            </fieldset>
          );
        }
        if (field.type === "select") {
          return (
            <div key={field.name} className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-ink">{field.label}</label>
              <select
                value={(values[field.name] as string) ?? ""}
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
            value={(values[field.name] as string) ?? ""}
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

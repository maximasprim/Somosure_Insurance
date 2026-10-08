"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export const kes = (v: string | number | null | undefined) =>
  v === null || v === undefined ? "-" : `KES ${Number(v).toLocaleString("en-KE", { maximumFractionDigits: 2 })}`;

export const CATEGORIES: { value: string; label: string }[] = [
  { value: "motor", label: "Motor" },
  { value: "medical", label: "Medical" },
  { value: "life", label: "Life" },
  { value: "travel", label: "Travel" },
  { value: "property", label: "Property" },
  { value: "personal_accident", label: "Personal accident" },
  { value: "professional_indemnity", label: "Professional indemnity" },
  { value: "wiba", label: "WIBA" },
];

export const categoryLabel = (value: string | null | undefined) =>
  value ? CATEGORIES.find((c) => c.value === value)?.label ?? value.replace(/_/g, " ") : "All products";

export interface PickedCustomer {
  id: string;
  full_name: string;
  phone: string;
  email: string | null;
}

/** Search-as-you-type picker for one customer (name, phone or email). */
export function CustomerPicker({
  value,
  onChange,
  placeholder = "Search by name, phone or email",
}: {
  value: PickedCustomer | null;
  onChange: (c: PickedCustomer | null) => void;
  placeholder?: string;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<PickedCustomer[]>([]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    const timer = setTimeout(() => {
      api
        .get<PickedCustomer[]>(`/api/v1/admin/affiliate-program/customers?q=${encodeURIComponent(q.trim())}`)
        .then(setResults)
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [q]);

  if (value) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-control border border-neutral-border bg-neutral/40 px-4 py-2 text-sm">
        <span>
          <span className="font-medium text-ink">{value.full_name}</span> <span className="text-ink-soft">{value.phone}</span>
        </span>
        <button type="button" onClick={() => onChange(null)} className="text-xs font-semibold text-brand-deep hover:underline">
          Change
        </button>
      </div>
    );
  }
  return (
    <div className="relative">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-control border border-neutral-border bg-white px-4 py-2 text-sm"
      />
      {results.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-control border border-neutral-border bg-white shadow">
          {results.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                className="w-full px-4 py-2 text-left text-sm hover:bg-neutral"
                onClick={() => {
                  onChange(c);
                  setQ("");
                  setResults([]);
                }}
              >
                <span className="font-medium text-ink">{c.full_name}</span>{" "}
                <span className="text-ink-soft">{c.phone}{c.email ? ` · ${c.email}` : ""}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-ink">{label}</label>
      <div className="mt-1.5">{children}</div>
      {hint && <p className="mt-1 text-xs text-ink-soft">{hint}</p>}
    </div>
  );
}

export const inputClass =
  "w-full rounded-control border border-neutral-border bg-white px-4 py-2 text-sm text-ink disabled:bg-neutral-tint/40 focus:outline-none focus:ring-2 focus:ring-brand-deep/40 focus:border-brand-deep";

"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

interface SearchResults {
  customers: { id: string; full_name: string; phone: string; email: string | null }[];
  quotes: { id: string; reference: string; category: string; status: string }[];
  policies: { id: string; policy_number: string; status: string }[];
  claims: { id: string; reference: string; status: string }[];
  applications: { id: string; reference: string; status: string }[];
  payments: { id: string; reference: string; status: string }[];
}

const SECTIONS: { key: keyof SearchResults; label: string }[] = [
  { key: "customers", label: "Customers" },
  { key: "quotes", label: "Quotes" },
  { key: "applications", label: "Applications" },
  { key: "policies", label: "Policies" },
  { key: "claims", label: "Claims" },
  { key: "payments", label: "Payments" },
];

export default function AdminSearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.get<SearchResults>(`/api/v1/admin/search?q=${encodeURIComponent(query)}`);
      setResults(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }

  const totalResults = results ? Object.values(results).reduce((sum, arr) => sum + arr.length, 0) : 0;

  return (
    <main className="mx-auto max-w-8xl px-6 py-12">
      <h1 className="text-2xl font-bold">Search</h1>
      <p className="mt-1 text-ink-soft">Find a customer, quote, application, policy, claim, or payment by reference.</p>

      <form onSubmit={handleSearch} className="mt-6 flex gap-3">
        <div className="flex-1">
          <Input placeholder="Phone, name, or reference number…" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
      </form>

      {error && <p className="mt-4 text-sm text-status-error">{error}</p>}
      {busy && <p className="mt-4 text-ink-soft">Searching…</p>}

      {results && (
        <div className="mt-6">
          <p className="mb-4 text-sm text-ink-soft">{totalResults} result{totalResults === 1 ? "" : "s"}</p>
          {SECTIONS.map(({ key, label }) => {
            const items = results[key];
            if (items.length === 0) return null;
            return (
              <div key={key} className="mb-6">
                <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-soft">{label}</h2>
                <div className="flex flex-col gap-2">
                  {items.map((item: any) => (
                    <Card key={item.id} className="flex items-center justify-between">
                      <span className="font-mono text-sm">
                        {item.reference ?? item.policy_number ?? item.full_name}
                        {item.phone && <span className="ml-2 font-sans text-ink-soft">{item.phone}</span>}
                      </span>
                      {item.status && <Badge tone="brand">{item.status.replace(/_/g, " ")}</Badge>}
                    </Card>
                  ))}
                </div>
              </div>
            );
          })}
          {totalResults === 0 && <p className="text-ink-soft">No matches found.</p>}
        </div>
      )}
    </main>
  );
}

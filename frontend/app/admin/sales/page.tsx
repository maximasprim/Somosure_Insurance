"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { AllSalesPanel } from "@/components/admin/sales/AllSalesPanel";
import { CustomersPanel } from "@/components/admin/sales/CustomersPanel";
import { RecordSalePanel } from "@/components/admin/sales/RecordSalePanel";
import { RenewalsPanel } from "@/components/admin/sales/RenewalsPanel";

const TABS = [
  { id: "sales", label: "All sales" },
  { id: "record", label: "Record a sale" },
  { id: "renewals", label: "Renewals" },
  { id: "customers", label: "Customers" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function AdminSalesPage() {
  const [tab, setTab] = useState<TabId>("sales");
  // A tab loads completely the first time it is opened (one placeholder, then everything at once) and is then kept, so
  // coming back to it is instant. Bumping `refreshKey` makes every opened tab reload after something changed.
  const [visited, setVisited] = useState<Set<TabId>>(new Set<TabId>(["sales"]));
  const [refreshKey, setRefreshKey] = useState(0);

  const open = (id: TabId) => {
    setTab(id);
    setVisited((prev) => (prev.has(id) ? prev : new Set(prev).add(id)));
  };
  const refresh = () => setRefreshKey((k) => k + 1);

  // /admin/sales?tab=renewals opens that tab (links from the dashboard use this).
  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("tab");
    if (TABS.some((t) => t.id === wanted)) open(wanted as TabId);
  }, []);

  const panel = (id: TabId) => {
    switch (id) {
      case "sales":
        return <AllSalesPanel refreshKey={refreshKey} />;
      case "record":
        return <RecordSalePanel onRecorded={refresh} />;
      case "renewals":
        return <RenewalsPanel refreshKey={refreshKey} onNeedPhones={() => { open("customers"); refresh(); }} />;
      case "customers":
        return <CustomersPanel refreshKey={refreshKey} />;
    }
  };

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Sales</h1>
          <p className="mt-1 text-sm text-ink-soft">
            Everything sold, whether it went through the platform or was recorded in the weekly report workbook.
          </p>
        </div>
        <a href="/admin/sales-import" className="text-sm text-brand-deep underline">Import the weekly report</a>
      </div>

      <div className="mt-5 flex flex-wrap gap-1 border-b border-neutral-border">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => open(t.id)}
            className={clsx(
              "-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors",
              tab === t.id ? "border-brand-deep text-ink" : "border-transparent text-ink-soft hover:text-ink"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {TABS.map((t) =>
          visited.has(t.id) ? (
            <div key={t.id} hidden={tab !== t.id}>
              {panel(t.id)}
            </div>
          ) : null
        )}
      </div>
    </main>
  );
}

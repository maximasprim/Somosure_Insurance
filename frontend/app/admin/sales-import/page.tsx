"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { AutomationPanel } from "@/components/admin/salesImport/AutomationPanel";
import { ClaimsIpfPanel } from "@/components/admin/salesImport/ClaimsIpfPanel";
import { ImportPanel } from "@/components/admin/salesImport/ImportPanel";
import { LedgerPanel } from "@/components/admin/salesImport/LedgerPanel";
import { NamesPanel } from "@/components/admin/salesImport/NamesPanel";
import { PostingPanel } from "@/components/admin/salesImport/PostingPanel";
import { SuggestionsPanel } from "@/components/admin/salesImport/SuggestionsPanel";
import { SummaryPanel } from "@/components/admin/salesImport/SummaryPanel";
import { VersionsPanel } from "@/components/admin/salesImport/VersionsPanel";

const TABS = [
  { id: "import", label: "Import" },
  { id: "auto", label: "Automation" },
  { id: "versions", label: "Versions" },
  { id: "post", label: "Post to system" },
  { id: "ledger", label: "Ledger" },
  { id: "summary", label: "Summary" },
  { id: "fixes", label: "Suggested fixes" },
  { id: "claims", label: "Claims & IPF" },
  { id: "names", label: "Names" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function AdminSalesImportPage() {
  const [tab, setTab] = useState<TabId>("import");
  // A tab loads completely the first time it is opened (one placeholder, then everything at once) and is then kept, so
  // coming back to it is instant - and an upload you were looking at is still there. `refreshKey` is bumped after an
  // import, a posting or a names change so every opened tab reloads its data.
  const [visited, setVisited] = useState<Set<TabId>>(new Set<TabId>(["import"]));
  const [refreshKey, setRefreshKey] = useState(0);

  const open = (id: TabId) => {
    setTab(id);
    setVisited((prev) => (prev.has(id) ? prev : new Set(prev).add(id)));
  };
  const refresh = () => setRefreshKey((k) => k + 1);

  useEffect(() => {
    const onOpen = (e: Event) => open(((e as CustomEvent).detail as TabId) ?? "post");
    window.addEventListener("sales-import-tab", onOpen);
    return () => window.removeEventListener("sales-import-tab", onOpen);
  }, []);

  const panel = (id: TabId) => {
    switch (id) {
      case "import":
        return <ImportPanel onImported={refresh} />;
      case "auto":
        return <AutomationPanel refreshKey={refreshKey} onImported={refresh} />;
      case "versions":
        return <VersionsPanel refreshKey={refreshKey} onReverted={refresh} />;
      case "post":
        return <PostingPanel refreshKey={refreshKey} onPosted={refresh} />;
      case "ledger":
        return <LedgerPanel refreshKey={refreshKey} />;
      case "summary":
        return <SummaryPanel refreshKey={refreshKey} />;
      case "fixes":
        return <SuggestionsPanel refreshKey={refreshKey} onApplied={refresh} />;
      case "claims":
        return <ClaimsIpfPanel refreshKey={refreshKey} />;
      case "names":
        return <NamesPanel refreshKey={refreshKey} onChanged={refresh} />;
    }
  };

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <h1 className="text-2xl font-bold">Sales import</h1>
      <p className="mt-1 text-ink-soft">
        Bring the weekly report workbook into the system and keep the two in step. Upload the whole workbook each time - only what changed is applied.
      </p>

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

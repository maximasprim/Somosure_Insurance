"use client";

import { useState } from "react";
import { AffiliatesTab } from "@/components/affiliate/AffiliatesTab";
import { CommissionsTab } from "@/components/affiliate/CommissionsTab";
import { DiscountsTab } from "@/components/affiliate/DiscountsTab";
import { RatesTab } from "@/components/affiliate/RatesTab";

const TABS = [
  { key: "commissions", label: "Commissions" },
  { key: "discounts", label: "Discounts" },
  { key: "rates", label: "Rates & settings" },
  { key: "affiliates", label: "Affiliates" },
] as const;

export default function AdminAffiliatesPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>("commissions");
  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <h1 className="text-2xl font-bold">Affiliate program</h1>
      <p className="mt-1 text-ink-soft">
        Reward people who refer customers. When someone they referred gets insured, they earn a commission at the rate you set here - and
        existing customers can be rewarded with a discount on their own insurance instead.
      </p>

      <div className="mt-6 flex gap-2 border-b border-neutral-border">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold ${tab === t.key ? "border-brand-deep text-ink" : "border-transparent text-ink-soft hover:text-ink"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === "commissions" && <CommissionsTab />}
        {tab === "discounts" && <DiscountsTab />}
        {tab === "rates" && <RatesTab />}
        {tab === "affiliates" && <AffiliatesTab />}
      </div>
    </main>
  );
}

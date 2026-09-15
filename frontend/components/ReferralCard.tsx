"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

interface Referral {
  code: string;
  status: string;
}

export function ReferralCard() {
  const [referral, setReferral] = useState<Referral | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get<Referral>("/api/v1/me/referral-code").then(setReferral).catch(() => {});
  }, []);

  if (!referral) return null;

  function handleCopy() {
    navigator.clipboard.writeText(referral!.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <section className="mt-8">
      <h2 className="text-lg font-semibold">Refer a friend</h2>
      <Card className="mt-3 flex items-center justify-between">
        <div>
          <p className="text-sm text-ink-soft">Share your code - they get help getting covered, you get rewarded.</p>
          <p className="mt-1 font-mono text-lg font-bold">{referral.code}</p>
        </div>
        <button onClick={handleCopy} className="rounded-control border border-neutral-border px-3 py-2 text-sm font-medium hover:bg-neutral">
          {copied ? "Copied!" : "Copy code"}
        </button>
      </Card>
    </section>
  );
}

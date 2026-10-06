"use client";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { STEP_LABEL, type SavedQuoteSession } from "@/lib/quoteSession";

/** "Welcome back" prompt shown above a fresh quote form when this browser
 *  has an unfinished quote from the last 24 hours. */
export function ResumeQuoteCard({
  saved,
  productLabel,
  onResume,
  onDiscard,
}: {
  saved: SavedQuoteSession;
  productLabel: string;
  onResume: () => void;
  onDiscard: () => void;
}) {
  return (
    <Card className="flex flex-col gap-3 border-brand-deep/30">
      <div>
        <h2 className="text-base font-bold">Pick up where you left off?</h2>
        <p className="mt-1 text-sm text-ink-soft">
          You have a {productLabel.toLowerCase()} quote in progress (reference{" "}
          <span className="font-semibold text-ink">{saved.application?.reference ?? saved.result.reference}</span>) - you were{" "}
          {STEP_LABEL[saved.step]}.
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button onClick={onResume}>Continue</Button>
        <Button variant="ghost" onClick={onDiscard}>
          Start over
        </Button>
      </div>
    </Card>
  );
}

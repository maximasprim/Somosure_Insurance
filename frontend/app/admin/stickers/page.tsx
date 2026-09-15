"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { StickerRecord } from "@/lib/types";

// Mirrors ALLOWED_TRANSITIONS in the backend (app/services/sticker_service.py)
// so the UI only ever offers valid next steps - the backend still enforces
// this independently, this is just for a sane button set.
const NEXT_STEPS: Record<string, string[]> = {
  pending: ["validated", "cancelled"],
  validated: ["payment_confirmed", "cancelled"],
  payment_confirmed: ["generating", "cancelled"],
  generating: ["generated"],
  generated: ["ready_for_collection"],
  ready_for_collection: ["dispatched"],
  dispatched: ["delivered", "replaced"],
  delivered: ["replaced"],
};

const STATUS_TONE: Record<string, "success" | "neutral" | "error" | "brand"> = {
  delivered: "success",
  cancelled: "error",
  pending: "neutral",
};

export default function StickerQueuePage() {
  const [stickers, setStickers] = useState<StickerRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api.get<StickerRecord[]>("/api/v1/admin/stickers");
      setStickers(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the sticker queue");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function advance(sticker: StickerRecord, toStatus: string) {
    await api.post(`/api/v1/admin/stickers/${sticker.id}/advance`, { to_status: toStatus });
    load();
  }

  if (error) return <main className="mx-auto max-w-4xl px-6 py-12 text-status-error">{error}</main>;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="text-2xl font-bold">Sticker issuance queue</h1>
      <p className="mt-1 text-ink-soft">
        Motor stickers auto-generate when a policy activates. Move each one through validation, generation, and
        dispatch - only the valid next step is offered at each stage.
      </p>

      <div className="mt-6 flex flex-col gap-3">
        {stickers.map((s) => (
          <Card key={s.id} className="flex items-center justify-between">
            <div>
              <p className="font-mono text-sm">{s.reference}</p>
              <Badge tone={STATUS_TONE[s.status] ?? "brand"}>{s.status.replace(/_/g, " ")}</Badge>
            </div>
            <div className="flex gap-2">
              {(NEXT_STEPS[s.status] ?? []).map((next) => (
                <Button key={next} size="md" variant={next === "cancelled" ? "ghost" : "primary"} onClick={() => advance(s, next)}>
                  {next.replace(/_/g, " ")}
                </Button>
              ))}
            </div>
          </Card>
        ))}
        {stickers.length === 0 && <p className="text-ink-soft">No stickers yet.</p>}
      </div>
    </main>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { referralLink } from "@/lib/referral";
import type { MyAffiliate } from "@/lib/types";

const kes = (v: string | number) => `KES ${Number(v).toLocaleString("en-KE", { maximumFractionDigits: 2 })}`;

const STATUS_TONE: Record<string, "success" | "error" | "brand" | "neutral" | "info"> = {
  pending: "info",
  approved: "brand",
  paid: "success",
  reversed: "error",
  rejected: "error",
};

/**
 * "Your referral earnings" on the customer dashboard. Renders nothing until the
 * program is switched on (or the customer already has earnings), so the
 * dashboard is exactly as it was until management launches the program.
 */
export function AffiliateCard() {
  const [data, setData] = useState<MyAffiliate | null>(null);
  const [copied, setCopied] = useState(false);
  const [phone, setPhone] = useState("");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<MyAffiliate>("/api/v1/me/affiliate").then((d) => { setData(d); setPhone(d.payout_phone ?? ""); }).catch(() => {});
  }, []);

  if (!data) return null;
  const hasActivity = data.commissions.length > 0 || data.referred > 0 || data.discounts.length > 0;
  if (!data.program_enabled && !hasActivity) return null;

  async function enroll() {
    setBusy(true);
    setError(null);
    try {
      const d = await api.post<MyAffiliate>("/api/v1/me/affiliate/enroll");
      setData(d);
      setPhone(d.payout_phone ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not join right now");
    } finally {
      setBusy(false);
    }
  }

  async function savePhone() {
    setBusy(true);
    setError(null);
    try {
      const d = await api.patch<MyAffiliate>("/api/v1/me/affiliate", { payout_phone: phone });
      setData(d);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save your number");
    } finally {
      setBusy(false);
    }
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const link = data.affiliate_code ? referralLink(data.affiliate_code) : null;

  return (
    <section className="mt-8">
      <h2 className="text-lg font-semibold">Your referral earnings</h2>
      <Card className="mt-3 flex flex-col gap-5">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="People referred" value={String(data.referred)} />
          <Stat label="Bought cover" value={String(data.converted)} />
          <Stat label="Awaiting payout" value={kes(Number(data.earned_pending) + Number(data.earned_approved))} />
          <Stat label="Paid to you" value={kes(data.earned_paid)} />
        </div>

        {data.is_affiliate && link && (
          <div className="rounded-control bg-neutral px-4 py-3">
            <p className="text-sm text-ink-soft">Your personal link - anyone who buys cover after opening it is credited to you, every time.</p>
            <p className="mt-1 break-all font-mono text-sm font-semibold">{link}</p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <Button variant="ghost" size="md" onClick={() => copy(link)}>{copied ? "Copied!" : "Copy link"}</Button>
              <span className="text-xs text-ink-soft">or share your code <span className="font-mono font-bold text-ink">{data.affiliate_code}</span></span>
              {data.affiliate_status === "suspended" && <Badge tone="error">Paused - contact us</Badge>}
            </div>
          </div>
        )}

        {data.can_self_enroll && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-control bg-neutral px-4 py-3">
            <p className="text-sm text-ink-soft">Refer often? Become an affiliate to get a personal link that works for everyone you share it with.</p>
            <Button onClick={enroll} disabled={busy}>{busy ? "Joining…" : "Become an affiliate"}</Button>
          </div>
        )}

        {data.is_affiliate && (
          <div className="text-sm">
            {editing ? (
              <div className="flex flex-wrap items-center gap-2">
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="M-Pesa number"
                  className="w-48 rounded-control border border-neutral-border bg-white px-3 py-2 text-sm"
                />
                <Button size="md" onClick={savePhone} disabled={busy}>Save</Button>
                <Button size="md" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
              </div>
            ) : (
              <p className="text-ink-soft">
                Payouts go to M-Pesa <span className="font-semibold text-ink">{data.payout_phone ?? "-"}</span>{" "}
                <button type="button" onClick={() => setEditing(true)} className="font-semibold text-brand-deep hover:underline">Change</button>
              </p>
            )}
          </div>
        )}
        {error && <p className="text-sm text-status-error">{error}</p>}

        {data.discounts.length > 0 && (
          <div>
            <p className="text-sm font-semibold">Your insurance discounts</p>
            <p className="mt-0.5 text-xs text-ink-soft">
              A thank-you for referring friends who bought cover. Tell us when you&apos;re buying or renewing and we&apos;ll apply it to your policy.
            </p>
            <div className="mt-2 flex flex-col divide-y divide-neutral-border">
              {data.discounts.map((d) => (
                <div key={d.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div>
                    <p className="font-medium text-ink">{d.description}</p>
                    <p className="text-xs text-ink-soft">
                      {d.status === "available" && d.expires_at ? `Use it by ${new Date(d.expires_at).toLocaleDateString()}` : d.status === "applied" && d.applied_amount ? `${kes(d.applied_amount)} taken off your policy` : d.note}
                    </p>
                  </div>
                  <Badge tone={d.status === "available" ? "success" : d.status === "applied" ? "brand" : "neutral"}>{d.status}</Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.commissions.length > 0 && (
          <div>
            <p className="text-sm font-semibold">Recent earnings</p>
            <div className="mt-2 flex flex-col divide-y divide-neutral-border">
              {data.commissions.map((c) => (
                <div key={c.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div>
                    <p className="font-medium text-ink">{c.referred_first_name ? `${c.referred_first_name} bought ` : "Cover bought "}{c.category ? c.category.replace(/_/g, " ") : "insurance"}</p>
                    <p className="text-xs text-ink-soft">{new Date(c.created_at).toLocaleDateString()}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{kes(c.commission_amount)}</span>
                    <Badge tone={STATUS_TONE[c.status] ?? "neutral"}>{c.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-ink-soft">{label}</p>
      <p className="mt-0.5 text-lg font-bold text-ink">{value}</p>
    </div>
  );
}

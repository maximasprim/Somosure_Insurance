"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { referralLink } from "@/lib/referral";
import type { PartnerApplication, PartnerApplicationPage, PartnerApplicationStatus, PartnerApprovalResult } from "@/lib/types";
import { Field, inputClass } from "@/components/affiliate/shared";
import { PARTNER_TYPES } from "@/components/partners/PartnerApplicationForm";

const BASE = "/api/v1/admin/partner-applications";
const PAGE = 25;
const TYPE_LABEL = Object.fromEntries(PARTNER_TYPES.map((t) => [t.value, t.label]));
const MODEL_LABEL: Record<string, string> = {
  referrals: "Refer customers to us",
  applications: "Submit applications for their customers",
  both: "Both - refer and submit applications",
};
const TONE: Record<PartnerApplicationStatus, "info" | "success" | "error"> = { pending: "info", approved: "success", declined: "error" };
const FILTERS: { key: "" | PartnerApplicationStatus; label: string }[] = [
  { key: "pending", label: "Waiting" },
  { key: "approved", label: "Approved" },
  { key: "declined", label: "Declined" },
  { key: "", label: "All" },
];

type Panel = { id: string; kind: "approve" | "decline" } | null;

export default function PartnerApplicationsPage() {
  const [status, setStatus] = useState<"" | PartnerApplicationStatus>("pending");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<PartnerApplicationPage | null>(null);
  const [panel, setPanel] = useState<Panel>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PartnerApprovalResult | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(
    async (next = 0) => {
      setError(null);
      try {
        const params = new URLSearchParams({ limit: String(PAGE), offset: String(next) });
        if (status) params.set("status", status);
        if (q.trim()) params.set("q", q.trim());
        setPage(await api.get<PartnerApplicationPage>(`${BASE}?${params}`));
        setOffset(next);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load partner applications");
      }
    },
    [status, q]
  );
  useEffect(() => {
    load(0);
  }, [load]);

  const items = page?.items ?? [];
  const total = page?.total ?? 0;

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <h1 className="text-2xl font-bold">Partner applications</h1>
      <p className="mt-1 text-ink-soft">
        Businesses that applied on the public &quot;Become a partner&quot; page. Approving one creates the partner (and can enrol them as an affiliate);
        approving or declining always needs a reason, which is kept on record.
      </p>

      <div className="mt-6 flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setStatus(f.key)}
            className={`rounded-full px-4 py-1.5 text-sm font-semibold ${status === f.key ? "bg-brand-deep text-white" : "bg-neutral text-ink-soft hover:text-ink"}`}
          >
            {f.label}
            {f.key === "pending" && page && page.pending_count > 0 ? ` (${page.pending_count})` : ""}
          </button>
        ))}
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(0)}
          placeholder="Search business, contact or reference"
          className={`${inputClass} ml-auto max-w-xs`}
        />
      </div>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      {result && (
        <Card className="mt-6 flex flex-col gap-2 border-status-success/40 bg-status-success/5">
          <p className="font-semibold text-status-success">
            {result.application.business_name} is now a partner{result.affiliate_code ? " and an affiliate" : ""}.
          </p>
          {result.affiliate_code && (
            <div className="text-sm">
              <p className="text-ink-soft">Their personal referral link (send it to {result.application.contact_name}):</p>
              <p className="mt-1 break-all font-mono font-semibold">{referralLink(result.affiliate_code)}</p>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(referralLink(result.affiliate_code!));
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                className="mt-1 text-xs font-semibold text-brand-deep hover:underline"
              >
                {copied ? "Copied!" : "Copy link"}
              </button>
              <p className="mt-2 text-xs text-ink-soft">
                {result.commission_rule_created ? "A special commission rate was set. " : ""}
                {result.discount_credit_created ? "A discount credit was given (Affiliates → Discounts). " : ""}
              </p>
            </div>
          )}
          {result.warnings.map((w) => (
            <p key={w} className="text-sm text-status-error">{w}</p>
          ))}
          <div><button type="button" onClick={() => setResult(null)} className="text-xs font-semibold text-ink-soft hover:underline">Dismiss</button></div>
        </Card>
      )}

      <div className="mt-6 flex flex-col gap-4">
        {items.map((a) => (
          <ApplicationCard
            key={a.id}
            application={a}
            panel={panel?.id === a.id ? panel.kind : null}
            onOpen={(kind) => { setPanel({ id: a.id, kind }); setResult(null); }}
            onClose={() => setPanel(null)}
            onDone={(res) => { setPanel(null); if (res) setResult(res); load(offset); }}
          />
        ))}
        {page && items.length === 0 && (
          <Card className="py-10 text-center text-ink-soft">
            {status === "pending" ? "No applications are waiting. New ones from the Become a partner page appear here." : "Nothing here yet."}
          </Card>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between text-sm text-ink-soft">
        <span>{total === 0 ? "0" : `${offset + 1}–${Math.min(offset + PAGE, total)} of ${total}`}</span>
        <div className="flex gap-2">
          <Button variant="ghost" disabled={offset === 0} onClick={() => load(Math.max(0, offset - PAGE))}>← Previous</Button>
          <Button variant="ghost" disabled={offset + PAGE >= total} onClick={() => load(offset + PAGE)}>Next →</Button>
        </div>
      </div>
    </main>
  );
}

function ApplicationCard({
  application: a,
  panel,
  onOpen,
  onClose,
  onDone,
}: {
  application: PartnerApplication;
  panel: "approve" | "decline" | null;
  onOpen: (kind: "approve" | "decline") => void;
  onClose: () => void;
  onDone: (result: PartnerApprovalResult | null) => void;
}) {
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-lg font-semibold text-ink">{a.business_name}</p>
          <p className="text-sm text-ink-soft">
            {TYPE_LABEL[a.partner_type] ?? a.partner_type}{a.town ? ` · ${a.town}` : ""} · <span className="font-mono">{a.reference}</span> · received{" "}
            {new Date(a.created_at).toLocaleString()}
          </p>
        </div>
        <Badge tone={TONE[a.status]}>{a.status === "pending" ? "waiting" : a.status}</Badge>
      </div>

      <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
        <div><dt className="inline font-medium">Contact: </dt><dd className="inline">{a.contact_name}</dd></div>
        <div><dt className="inline font-medium">Phone: </dt><dd className="inline"><a href={`tel:${a.contact_phone}`} className="text-brand-deep hover:underline">{a.contact_phone}</a></dd></div>
        <div><dt className="inline font-medium">Email: </dt><dd className="inline"><a href={`mailto:${a.contact_email}`} className="text-brand-deep hover:underline">{a.contact_email}</a></dd></div>
        {a.website && <div><dt className="inline font-medium">Website: </dt><dd className="inline break-all">{a.website}</dd></div>}
        <div><dt className="inline font-medium">Would like to: </dt><dd className="inline">{MODEL_LABEL[a.working_model] ?? a.working_model}</dd></div>
        <div><dt className="inline font-medium">Customers a month: </dt><dd className="inline">{a.monthly_clients}</dd></div>
        {a.products && a.products.length > 0 && (
          <div className="sm:col-span-2"><dt className="inline font-medium">Interested in: </dt><dd className="inline">{a.products.map((p) => p.replace(/_/g, " ")).join(", ")}</dd></div>
        )}
      </dl>
      <p className="rounded-control bg-neutral px-4 py-3 text-sm text-ink">{a.message}</p>

      {a.status !== "pending" && (
        <p className="text-sm text-ink-soft">
          {a.status === "approved" ? "Approved" : "Declined"}
          {a.decided_at ? ` on ${new Date(a.decided_at).toLocaleDateString()}` : ""}: “{a.decision_reason}”
          {a.affiliate_code && <> · affiliate code <span className="font-mono font-semibold text-ink">{a.affiliate_code}</span></>}
          {a.partner_id && <> · <a href="/admin/partners" className="font-semibold text-brand-deep hover:underline">see in Partners</a></>}
        </p>
      )}

      {a.status === "pending" && !panel && (
        <div className="flex gap-3">
          <Button onClick={() => onOpen("approve")}>Approve…</Button>
          <Button variant="ghost" onClick={() => onOpen("decline")}>Decline…</Button>
        </div>
      )}
      {panel === "decline" && <DeclinePanel application={a} onClose={onClose} onDone={() => onDone(null)} />}
      {panel === "approve" && <ApprovePanel application={a} onClose={onClose} onDone={onDone} />}
    </Card>
  );
}

function DeclinePanel({ application, onClose, onDone }: { application: PartnerApplication; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decline() {
    setBusy(true);
    setError(null);
    try {
      await api.post(`${BASE}/${application.id}/decline`, { reason }, { reason });
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not decline");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-control bg-neutral/60 p-4">
      <Field label="Why are you declining this application?" hint="Kept on record. It isn't sent to the applicant automatically - contact them yourself if appropriate.">
        <input autoFocus value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. We don't serve that area yet" className={inputClass} />
      </Field>
      {error && <p className="text-sm text-status-error">{error}</p>}
      <div className="flex gap-3">
        <Button disabled={busy || reason.trim().length < 3} onClick={decline}>{busy ? "Declining…" : "Decline application"}</Button>
        <Button variant="ghost" onClick={onClose}>Back</Button>
      </div>
    </div>
  );
}

function ApprovePanel({ application, onClose, onDone }: { application: PartnerApplication; onClose: () => void; onDone: (r: PartnerApprovalResult) => void }) {
  const [reason, setReason] = useState("");
  const [type, setType] = useState(application.partner_type);
  const [enrol, setEnrol] = useState(false);
  const [commType, setCommType] = useState<"percent" | "fixed">("percent");
  const [commValue, setCommValue] = useState("");
  const [discType, setDiscType] = useState<"percent" | "fixed">("percent");
  const [discValue, setDiscValue] = useState("");
  const [discDays, setDiscDays] = useState("365");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function approve() {
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { reason, partner_type: type !== application.partner_type ? type : undefined, enrol_affiliate: enrol };
      if (enrol && commValue !== "") { body.commission_type = commType; body.commission_value = commValue; }
      if (enrol && discValue !== "") { body.discount_type = discType; body.discount_value = discValue; body.discount_valid_days = Number(discDays) || 365; }
      onDone(await api.post<PartnerApprovalResult>(`${BASE}/${application.id}/approve`, body, { reason }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not approve");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-control bg-neutral/60 p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Reason for approving" hint="Kept on record.">
          <input autoFocus value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Established dealer with good volumes" className={inputClass} />
        </Field>
        <Field label="Partner type" hint="Change it if they chose the wrong one.">
          <select value={type} onChange={(e) => setType(e.target.value)} className={inputClass}>
            {PARTNER_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </Field>
      </div>

      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-0.5" checked={enrol} onChange={(e) => setEnrol(e.target.checked)} />
        <span>
          <span className="font-medium text-ink">Also enrol {application.contact_name} as an affiliate</span>{" "}
          <span className="text-ink-soft">- gives them a personal referral link and code, so customers they send you are credited to them.</span>
        </span>
      </label>

      {enrol && (
        <div className="grid gap-4 border-l-2 border-brand-deep/30 pl-4 sm:grid-cols-2">
          <Field label="Special commission rate (optional)" hint="Leave blank to use the program's normal rate.">
            <div className="flex gap-2">
              <select value={commType} onChange={(e) => setCommType(e.target.value as "percent" | "fixed")} className={`${inputClass} max-w-[9rem]`}>
                <option value="percent">% of premium</option>
                <option value="fixed">KES per policy</option>
              </select>
              <input type="number" min="0" step="0.01" value={commValue} onChange={(e) => setCommValue(e.target.value)} className={`${inputClass} max-w-[7rem]`} />
            </div>
          </Field>
          <Field label="Insurance discount credit (optional)" hint="A one-off credit you can apply to their own insurance (Affiliates → Discounts).">
            <div className="flex gap-2">
              <select value={discType} onChange={(e) => setDiscType(e.target.value as "percent" | "fixed")} className={`${inputClass} max-w-[7rem]`}>
                <option value="percent">% off</option>
                <option value="fixed">KES off</option>
              </select>
              <input type="number" min="0" step="0.01" value={discValue} onChange={(e) => setDiscValue(e.target.value)} className={`${inputClass} max-w-[6rem]`} />
              <input type="number" min="1" value={discDays} onChange={(e) => setDiscDays(e.target.value)} title="Days it stays usable" className={`${inputClass} max-w-[5rem]`} />
              <span className="self-center text-xs text-ink-soft">days</span>
            </div>
          </Field>
        </div>
      )}

      {error && <p className="text-sm text-status-error">{error}</p>}
      <div className="flex gap-3">
        <Button disabled={busy || reason.trim().length < 3} onClick={approve}>{busy ? "Approving…" : "Approve and create partner"}</Button>
        <Button variant="ghost" onClick={onClose}>Back</Button>
      </div>
    </div>
  );
}

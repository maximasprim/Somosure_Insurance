"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import {
  IPF_TYPE_HELP,
  formatDay,
  kes,
  type IpfDetail,
  type LoanOfficerSummary,
} from "@/lib/ipf";

const INPUT = "w-full rounded-control border border-neutral-border bg-white px-3 py-2 text-sm";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-neutral-border/60 py-3 last:border-0">
      <span className="text-sm font-medium text-ink">{label}</span>
      <div className="flex min-w-0 flex-wrap items-center justify-end gap-2 text-sm">{children}</div>
    </div>
  );
}

/**
 * Everything IPF-specific on one financing request: linked/unlinked, the physical
 * security (original logbook, tracker, post-dated cheques), the loan officer who
 * brought the sale in, and early settlement. Loads and saves on its own, so the
 * rest of the financing screen is untouched. `onChanged` lets the page refresh.
 */
export function IpfPanels({
  applicationId,
  status,
  onChanged,
}: {
  applicationId: string;
  status: string;
  onChanged?: () => void;
}) {
  const base = `/api/v1/admin/financing/applications/${applicationId}`;
  const [detail, setDetail] = useState<IpfDetail | null>(null);
  const [officers, setOfficers] = useState<LoanOfficerSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [tracker, setTracker] = useState({ provider: "", device_id: "" });
  const [cheque, setCheque] = useState({ cheque_number: "", bank_name: "", amount: "", cheque_date: "" });
  const [settle, setSettle] = useState({ payment_reference: "", notes: "" });
  const [confirmSettle, setConfirmSettle] = useState(false);

  const load = useCallback(async () => {
    try {
      setDetail(await api.get<IpfDetail>(`${base}/ipf`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the IPF details");
    }
  }, [base]);

  useEffect(() => {
    load();
    api
      .get<LoanOfficerSummary[]>("/api/v1/admin/loan-officers")
      .then(setOfficers)
      .catch(() => setOfficers([]));
  }, [load, status]);

  async function act(work: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await work();
      await load();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work - please try again");
    } finally {
      setBusy(false);
    }
  }

  if (!detail) {
    return error ? <p className="text-sm text-status-error">{error}</p> : null;
  }

  const activeOfficers = officers.filter((o) => o.is_active);
  const quote = detail.early_settlement;
  const showCheques = detail.cheques_required > 0 || detail.cheques.length > 0;
  const showTracker = detail.tracker.required || detail.tracker.installed;

  return (
    <>
      {error && <p className="text-sm text-status-error">{error}</p>}

      <Card>
        <h2 className="font-semibold">IPF security &amp; physical documents</h2>
        <p className="mt-1 text-xs text-ink-soft">
          What Bidii Credit holds against this financing, besides the uploaded documents.
        </p>

        <div className="mt-3">
          <Row label="IPF type">
            <div className="inline-flex rounded-control border border-neutral-border p-0.5" role="group">
              {(["unlinked", "linked"] as const).map((type) => (
                <button
                  key={type}
                  type="button"
                  disabled={busy}
                  onClick={() => detail.ipf_type !== type && act(() => api.post(`${base}/ipf-type`, { ipf_type: type }))}
                  className={`rounded-[8px] px-3 py-1 text-xs font-semibold capitalize ${
                    detail.ipf_type === type ? "bg-ink text-white" : "text-ink-soft hover:bg-neutral"
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </Row>
          <p className="pb-2 text-xs text-ink-soft">{IPF_TYPE_HELP[detail.ipf_type]}</p>

          <Row label="Original logbook">
            {detail.original_logbook_received_at ? (
              <>
                <Badge tone="success">Received {formatDay(detail.original_logbook_received_at)}</Badge>
                <Button variant="ghost" disabled={busy} onClick={() => act(() => api.post(`${base}/original-logbook`, { received: false }))}>
                  Undo
                </Button>
              </>
            ) : (
              <>
                <Badge tone="brand">Not yet received</Badge>
                <Button variant="ghost" disabled={busy} onClick={() => act(() => api.post(`${base}/original-logbook`, { received: true }))}>
                  Mark received
                </Button>
              </>
            )}
          </Row>

          {showTracker && (
            <div className="border-b border-neutral-border/60 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-sm font-medium text-ink">Vehicle tracker</span>
                {detail.tracker.installed ? (
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <Badge tone="success">
                      {detail.tracker.provider} · {detail.tracker.device_id}
                    </Badge>
                    <Button variant="ghost" disabled={busy} onClick={() => act(() => api.post(`${base}/tracker`, { installed: false }))}>
                      Clear
                    </Button>
                  </div>
                ) : (
                  <Badge tone="brand">Required - not installed</Badge>
                )}
              </div>
              {!detail.tracker.installed && (
                <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                  <input className={INPUT} placeholder="Tracker company" value={tracker.provider} onChange={(e) => setTracker({ ...tracker, provider: e.target.value })} />
                  <input className={INPUT} placeholder="Device ID" value={tracker.device_id} onChange={(e) => setTracker({ ...tracker, device_id: e.target.value })} />
                  <Button
                    disabled={busy || !tracker.provider.trim() || !tracker.device_id.trim()}
                    onClick={() => act(() => api.post(`${base}/tracker`, { installed: true, ...tracker }))}
                  >
                    Confirm installed
                  </Button>
                </div>
              )}
            </div>
          )}

          {showCheques && (
            <div className="py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-sm font-medium text-ink">Post-dated cheques</span>
                <Badge tone={detail.cheques_received >= detail.cheques_required ? "success" : "brand"}>
                  {detail.cheques_received} of {detail.cheques_required} received
                </Badge>
              </div>

              {detail.cheques.length > 0 && (
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-ink-soft">
                      <tr>
                        <th className="py-1 pr-3 font-medium">Cheque</th>
                        <th className="py-1 pr-3 font-medium">Bank</th>
                        <th className="py-1 pr-3 font-medium">Dated</th>
                        <th className="py-1 pr-3 text-right font-medium">Amount</th>
                        <th className="py-1 font-medium">Status</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {detail.cheques.map((c) => (
                        <tr key={c.id} className="border-t border-neutral-border/60">
                          <td className="py-1.5 pr-3 font-medium text-ink">{c.cheque_number}</td>
                          <td className="py-1.5 pr-3">{c.bank_name}</td>
                          <td className="py-1.5 pr-3">{formatDay(c.cheque_date)}</td>
                          <td className="py-1.5 pr-3 text-right">{kes(c.amount)}</td>
                          <td className="py-1.5 pr-3">
                            <select
                              value={c.status}
                              disabled={busy}
                              onChange={(e) => act(() => api.patch(`${base}/cheques/${c.id}`, { status: e.target.value }))}
                              className="rounded-control border border-neutral-border bg-white px-1.5 py-1 text-xs"
                            >
                              <option value="received">Received</option>
                              <option value="banked">Banked</option>
                              <option value="bounced">Bounced</option>
                              <option value="returned">Returned</option>
                            </select>
                          </td>
                          <td className="py-1.5 text-right">
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => window.confirm("Remove this cheque from the record?") && act(() => api.del(`${base}/cheques/${c.id}`))}
                              className="text-status-error hover:underline"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_1fr_1fr_auto]">
                <input className={INPUT} placeholder="Cheque no." value={cheque.cheque_number} onChange={(e) => setCheque({ ...cheque, cheque_number: e.target.value })} />
                <input className={INPUT} placeholder="Bank" value={cheque.bank_name} onChange={(e) => setCheque({ ...cheque, bank_name: e.target.value })} />
                <input className={INPUT} type="number" min="0" placeholder="Amount (KES)" value={cheque.amount} onChange={(e) => setCheque({ ...cheque, amount: e.target.value })} />
                <input className={INPUT} type="date" value={cheque.cheque_date} onChange={(e) => setCheque({ ...cheque, cheque_date: e.target.value })} />
                <Button
                  disabled={busy || !cheque.cheque_number.trim() || !cheque.bank_name.trim() || !cheque.amount || !cheque.cheque_date}
                  onClick={() =>
                    act(async () => {
                      await api.post(`${base}/cheques`, { ...cheque, amount: cheque.amount });
                      setCheque({ cheque_number: "", bank_name: "", amount: "", cheque_date: "" });
                    })
                  }
                >
                  Add
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <h2 className="font-semibold">Loan officer</h2>
        <p className="mt-1 text-xs text-ink-soft">
          The Bidii Credit officer credited with this sale. They earn a share of Somosure&apos;s net commission once the financed policy is issued.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select
            className={`${INPUT} max-w-xs`}
            disabled={busy}
            value={detail.loan_officer?.id ?? ""}
            onChange={(e) => act(() => api.post(`${base}/loan-officer`, { loan_officer_id: e.target.value || null }))}
          >
            <option value="">No loan officer</option>
            {detail.loan_officer && !activeOfficers.some((o) => o.id === detail.loan_officer!.id) && (
              <option value={detail.loan_officer.id}>{detail.loan_officer.full_name} (inactive)</option>
            )}
            {activeOfficers.map((o) => (
              <option key={o.id} value={o.id}>
                {o.full_name} ({o.staff_number})
              </option>
            ))}
          </select>
          {detail.commission && (
            <Badge tone={detail.commission.status === "paid" ? "success" : "brand"}>
              Commission {detail.commission.commission_amount ? kes(detail.commission.commission_amount) : "awaiting net commission"} · {detail.commission.status.replace(/_/g, " ")}
            </Badge>
          )}
        </div>
        {officers.length === 0 && (
          <p className="mt-2 text-xs text-ink-soft">No loan officers yet - add them under Loan officers in the menu.</p>
        )}
      </Card>

      {(quote || detail.settlement) && (
        <Card>
          <h2 className="font-semibold">Early settlement</h2>
          {detail.settlement ? (
            <div className="mt-3 text-sm">
              <Badge tone="success">Settled {formatDay(detail.settlement.settled_at)}</Badge>
              <dl className="mt-3 grid grid-cols-2 gap-y-1.5 text-sm">
                <dt className="text-ink-soft">Paid to clear the loan</dt>
                <dd className="text-right font-semibold">{kes(detail.settlement.total_paid)}</dd>
                <dt className="text-ink-soft">Principal outstanding</dt>
                <dd className="text-right">{kes(detail.settlement.outstanding_principal)}</dd>
                <dt className="text-ink-soft">Early settlement fee ({detail.settlement.fee_pct}%)</dt>
                <dd className="text-right">{kes(detail.settlement.fee_amount)}</dd>
                <dt className="text-ink-soft">Would have paid on schedule</dt>
                <dd className="text-right">{kes(detail.settlement.would_have_paid)}</dd>
                {detail.settlement.payment_reference && (
                  <>
                    <dt className="text-ink-soft">Payment reference</dt>
                    <dd className="text-right">{detail.settlement.payment_reference}</dd>
                  </>
                )}
              </dl>
            </div>
          ) : quote && quote.eligible ? (
            <div className="mt-3">
              <p className="text-xs text-ink-soft">
                If the client clears the loan now they pay the principal still outstanding plus a {quote.fee_pct}% fee. The interest and fees still to come are waived.
              </p>
              <dl className="mt-3 grid grid-cols-2 gap-y-1.5 text-sm">
                <dt className="text-ink-soft">Instalments remaining</dt>
                <dd className="text-right">{quote.instalments_remaining}</dd>
                <dt className="text-ink-soft">Principal outstanding</dt>
                <dd className="text-right">{kes(quote.outstanding_principal)}</dd>
                <dt className="text-ink-soft">Fee ({quote.fee_pct}%)</dt>
                <dd className="text-right">{kes(quote.fee_amount)}</dd>
                <dt className="font-semibold text-ink">Client pays now</dt>
                <dd className="text-right text-base font-bold">{kes(quote.total_due)}</dd>
                <dt className="text-ink-soft">On schedule they would pay</dt>
                <dd className="text-right">{kes(quote.would_have_paid)}</dd>
                <dt className="text-ink-soft">Client saves</dt>
                <dd className="text-right text-status-success">{kes(quote.saving)}</dd>
              </dl>
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                <input className={INPUT} placeholder="Payment reference (e.g. M-Pesa code)" value={settle.payment_reference} onChange={(e) => setSettle({ ...settle, payment_reference: e.target.value })} />
                <input className={INPUT} placeholder="Notes (optional)" value={settle.notes} onChange={(e) => setSettle({ ...settle, notes: e.target.value })} />
              </div>
              <div className="mt-3 flex items-center gap-3">
                {!confirmSettle ? (
                  <Button variant="ghost" disabled={busy} onClick={() => setConfirmSettle(true)}>
                    Record early settlement
                  </Button>
                ) : (
                  <>
                    <span className="text-xs text-ink-soft">This waives the remaining instalments and closes the loan. It can&apos;t be undone.</span>
                    <Button
                      disabled={busy}
                      onClick={() => act(() => api.post(`${base}/early-settlement`, settle)).then(() => setConfirmSettle(false))}
                    >
                      Yes, record it
                    </Button>
                    <Button variant="ghost" onClick={() => setConfirmSettle(false)}>
                      Cancel
                    </Button>
                  </>
                )}
              </div>
            </div>
          ) : (
            <p className="mt-2 text-sm text-ink-soft">{quote?.reason}</p>
          )}
        </Card>
      )}
    </>
  );
}

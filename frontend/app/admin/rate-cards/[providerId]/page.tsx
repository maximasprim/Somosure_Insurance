"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

interface VehicleClass {
  id: string;
  product_category: string;
  code: string;
  label: string;
  min_sum_insured: string | null;
  data_confidence: string;
  source_document: string | null;
  notes: string | null;
  is_active: boolean;
}

interface Tier {
  id: string;
  vehicle_class_id: string;
  cover_type: string;
  band_unit: string;
  subtype_key: string | null;
  min_value: string | null;
  max_value: string | null;
  rate_percent: string | null;
  flat_amount: string | null;
  min_premium: string | null;
  label: string | null;
  tier_order: number;
}

interface ClassDetail extends VehicleClass {
  tiers: Tier[];
  extensions: unknown[];
  excesses: unknown[];
}

const emptyTierDraft = {
  cover_type: "comprehensive",
  band_unit: "sum_insured",
  min_value: "",
  max_value: "",
  rate_percent: "",
  flat_amount: "",
  min_premium: "",
  label: "",
};

export default function RateCardProviderDetailPage({ params }: { params: { providerId: string } }) {
  const { providerId } = params;
  const [classes, setClasses] = useState<VehicleClass[]>([]);
  const [expanded, setExpanded] = useState<Record<string, ClassDetail>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newClass, setNewClass] = useState({ code: "", label: "", min_sum_insured: "" });
  const [tierDrafts, setTierDrafts] = useState<Record<string, typeof emptyTierDraft>>({});

  const [previewAnswers, setPreviewAnswers] = useState('{\n  "value": 800000,\n  "usage": "private",\n  "cover_type": "comprehensive"\n}');
  const [previewResult, setPreviewResult] = useState<Record<string, unknown> | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    const data = await api.get<VehicleClass[]>(`/api/v1/admin/rate-cards/providers/${providerId}/classes`);
    setClasses(data);
    setLoading(false);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerId]);

  async function toggleExpand(classId: string) {
    if (expanded[classId]) {
      const next = { ...expanded };
      delete next[classId];
      setExpanded(next);
      return;
    }
    const detail = await api.get<ClassDetail>(`/api/v1/admin/rate-cards/classes/${classId}`);
    setExpanded((prev) => ({ ...prev, [classId]: detail }));
  }

  async function refreshClass(classId: string) {
    const detail = await api.get<ClassDetail>(`/api/v1/admin/rate-cards/classes/${classId}`);
    setExpanded((prev) => ({ ...prev, [classId]: detail }));
  }

  async function handleCreateClass() {
    if (!newClass.code.trim() || !newClass.label.trim()) return;
    setError(null);
    try {
      await api.post(`/api/v1/admin/rate-cards/providers/${providerId}/classes`, {
        code: newClass.code.trim(),
        label: newClass.label.trim(),
        min_sum_insured: newClass.min_sum_insured ? Number(newClass.min_sum_insured) : null,
        tiers: [],
      });
      setNewClass({ code: "", label: "", min_sum_insured: "" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create class");
    }
  }

  function tierDraftFor(classId: string) {
    return tierDrafts[classId] ?? emptyTierDraft;
  }

  async function handleAddTier(classId: string) {
    const draft = tierDraftFor(classId);
    setError(null);
    try {
      await api.post(`/api/v1/admin/rate-cards/classes/${classId}/tiers`, {
        cover_type: draft.cover_type,
        band_unit: draft.band_unit,
        min_value: draft.min_value ? Number(draft.min_value) : null,
        max_value: draft.max_value ? Number(draft.max_value) : null,
        rate_percent: draft.rate_percent ? Number(draft.rate_percent) : null,
        flat_amount: draft.flat_amount ? Number(draft.flat_amount) : null,
        min_premium: draft.min_premium ? Number(draft.min_premium) : null,
        label: draft.label || null,
      });
      setTierDrafts((prev) => ({ ...prev, [classId]: emptyTierDraft }));
      await refreshClass(classId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add tier");
    }
  }

  async function handleDeleteTier(classId: string, tierId: string) {
    await api.del(`/api/v1/admin/rate-cards/tiers/${tierId}`);
    await refreshClass(classId);
  }

  async function handlePreview() {
    setPreviewError(null);
    setPreviewResult(null);
    try {
      const answers = JSON.parse(previewAnswers);
      const result = await api.post<Record<string, unknown>>(`/api/v1/admin/rate-cards/providers/${providerId}/preview`, {
        answers,
      });
      setPreviewResult(result);
    } catch (e) {
      setPreviewError(e instanceof Error ? e.message : "Preview failed - check the JSON is valid");
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-2xl font-bold">Vehicle classes</h1>
      <p className="mt-1 text-ink-soft">
        Every number a customer&apos;s quote is computed from for this provider. Add tiers for a sum-insured band,
        a tonnage/passenger band, or a flat amount - see docs/RATE_CARDS.md for what each field means.
      </p>

      {error && <div className="mt-4 rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}

      <Card className="mt-6">
        <h2 className="font-semibold">Live preview</h2>
        <p className="mt-1 text-xs text-ink-soft">
          Paste quote-form-shaped answers to sanity-check pricing immediately after an edit.
        </p>
        <textarea
          className="mt-3 w-full rounded-control border border-neutral-border bg-white p-3 font-mono text-xs"
          rows={6}
          value={previewAnswers}
          onChange={(e) => setPreviewAnswers(e.target.value)}
        />
        <Button className="mt-3" variant="ghost" onClick={handlePreview}>
          Run preview
        </Button>
        {previewError && <p className="mt-2 text-sm text-status-error">{previewError}</p>}
        {previewResult && (
          <pre className="mt-3 overflow-x-auto rounded-control bg-neutral p-3 text-xs">{JSON.stringify(previewResult, null, 2)}</pre>
        )}
      </Card>

      <Card className="mt-6 grid gap-3 sm:grid-cols-3">
        <Input label="Class code" placeholder="motor_private" value={newClass.code} onChange={(e) => setNewClass({ ...newClass, code: e.target.value })} />
        <Input label="Label" placeholder="Motor Private (070)" value={newClass.label} onChange={(e) => setNewClass({ ...newClass, label: e.target.value })} />
        <Input
          label="Min sum insured (optional)"
          type="number"
          value={newClass.min_sum_insured}
          onChange={(e) => setNewClass({ ...newClass, min_sum_insured: e.target.value })}
        />
        <Button onClick={handleCreateClass} className="sm:col-span-3">
          Add vehicle class
        </Button>
      </Card>

      <div className="mt-6 flex flex-col gap-3">
        {loading && <p className="text-ink-soft">Loading…</p>}
        {!loading &&
          classes.map((c) => (
            <Card key={c.id}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{c.label}</h3>
                    <Badge tone="neutral">{c.code}</Badge>
                    <Badge tone={c.data_confidence === "verified" ? "success" : "error"}>{c.data_confidence}</Badge>
                  </div>
                  {c.source_document && <p className="mt-1 text-xs text-ink-soft">{c.source_document}</p>}
                </div>
                <Button variant="ghost" onClick={() => toggleExpand(c.id)}>
                  {expanded[c.id] ? "Hide tiers" : "Show tiers"}
                </Button>
              </div>

              {expanded[c.id] && (
                <div className="mt-4 border-t border-neutral-border pt-4">
                  <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <thead className="text-xs uppercase text-ink-soft">
                      <tr>
                        <th className="pb-2">Cover</th>
                        <th className="pb-2">Band</th>
                        <th className="pb-2">Range</th>
                        <th className="pb-2">Rate %</th>
                        <th className="pb-2">Flat</th>
                        <th className="pb-2">Min premium</th>
                        <th className="pb-2">Label</th>
                        <th className="pb-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {expanded[c.id].tiers.map((t) => (
                        <tr key={t.id} className="border-t border-neutral-border">
                          <td className="py-1.5">{t.cover_type}</td>
                          <td className="py-1.5">{t.band_unit}</td>
                          <td className="py-1.5">
                            {t.min_value ?? "—"} - {t.max_value ?? "∞"}
                          </td>
                          <td className="py-1.5">{t.rate_percent ?? "—"}</td>
                          <td className="py-1.5">{t.flat_amount ?? "—"}</td>
                          <td className="py-1.5">{t.min_premium ?? "—"}</td>
                          <td className="py-1.5">{t.label ?? "—"}</td>
                          <td className="py-1.5">
                            <button className="text-xs text-status-error" onClick={() => handleDeleteTier(c.id, t.id)}>
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>

                  <div className="mt-4 grid gap-2 sm:grid-cols-4">
                    <select
                      className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                      value={tierDraftFor(c.id).cover_type}
                      onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), cover_type: e.target.value } }))}
                    >
                      <option value="comprehensive">Comprehensive</option>
                      <option value="tpo">TPO</option>
                    </select>
                    <select
                      className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                      value={tierDraftFor(c.id).band_unit}
                      onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), band_unit: e.target.value } }))}
                    >
                      <option value="sum_insured">Sum insured</option>
                      <option value="tonnes">Tonnes</option>
                      <option value="passengers">Passengers</option>
                      <option value="subtype">Subtype</option>
                      <option value="none">None (flat)</option>
                    </select>
                    <input
                      className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                      placeholder="Min"
                      value={tierDraftFor(c.id).min_value}
                      onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), min_value: e.target.value } }))}
                    />
                    <input
                      className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                      placeholder="Max (blank = unbounded)"
                      value={tierDraftFor(c.id).max_value}
                      onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), max_value: e.target.value } }))}
                    />
                    <input
                      className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                      placeholder="Rate %"
                      value={tierDraftFor(c.id).rate_percent}
                      onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), rate_percent: e.target.value } }))}
                    />
                    <input
                      className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                      placeholder="Flat amount"
                      value={tierDraftFor(c.id).flat_amount}
                      onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), flat_amount: e.target.value } }))}
                    />
                    <input
                      className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                      placeholder="Min premium"
                      value={tierDraftFor(c.id).min_premium}
                      onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), min_premium: e.target.value } }))}
                    />
                    <input
                      className="rounded-control border border-neutral-border px-3 py-2 text-sm"
                      placeholder="Label"
                      value={tierDraftFor(c.id).label}
                      onChange={(e) => setTierDrafts((prev) => ({ ...prev, [c.id]: { ...tierDraftFor(c.id), label: e.target.value } }))}
                    />
                  </div>
                  <Button variant="ghost" className="mt-2" onClick={() => handleAddTier(c.id)}>
                    Add tier
                  </Button>
                </div>
              )}
            </Card>
          ))}
      </div>
    </main>
  );
}

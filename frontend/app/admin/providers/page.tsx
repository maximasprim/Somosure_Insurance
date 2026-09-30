"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

interface Provider {
  id: string;
  name: string;
  provider_type: string;
  integration_mode: string;
  status: string;
  supports_quote: boolean;
  supports_policy: boolean;
  supports_payment: boolean;
  supports_documents: boolean;
  supports_claims: boolean;
  supports_renewal: boolean;
  supports_webhooks: boolean;
}

type ProviderEdits = Partial<Pick<Provider, "name" | "provider_type" | "integration_mode" | "status">> & {
  supports_quote?: boolean;
  supports_policy?: boolean;
  supports_payment?: boolean;
  supports_documents?: boolean;
  supports_claims?: boolean;
  supports_renewal?: boolean;
  supports_webhooks?: boolean;
};

const statusTone: Record<string, "success" | "neutral" | "error"> = {
  active: "success",
  inactive: "neutral",
  maintenance: "error",
  manual_only: "neutral",
};

const SUPPORT_FLAGS: { key: keyof Provider; label: string }[] = [
  { key: "supports_quote", label: "Quote" },
  { key: "supports_policy", label: "Policy" },
  { key: "supports_payment", label: "Payment" },
  { key: "supports_documents", label: "Documents" },
  { key: "supports_claims", label: "Claims" },
  { key: "supports_renewal", label: "Renewal" },
  { key: "supports_webhooks", label: "Webhooks" },
];

// Small centered dialog. Clicking the backdrop or pressing Escape calls onClose.
function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={onClose} role="presentation">
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-control bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

export default function AdminProvidersPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ProviderEdits>({});
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleteBlocked, setDeleteBlocked] = useState<string | null>(null);
  const [forceDeleteId, setForceDeleteId] = useState<string | null>(null);
  const [forceConfirmText, setForceConfirmText] = useState("");
  const [forceBusy, setForceBusy] = useState(false);
  const [forceResult, setForceResult] = useState<string | null>(null);

  const deleteTarget = providers.find((p) => p.id === confirmDeleteId) ?? null;

  async function load() {
    setLoading(true);
    const data = await api.get<Provider[]>("/api/v1/admin/providers");
    setProviders(data);
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await api.post("/api/v1/admin/providers", { name: newName, provider_type: "insurer", integration_mode: "mock" });
      setNewName("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add provider");
    } finally {
      setCreating(false);
    }
  }

  async function toggleStatus(provider: Provider) {
    const next = provider.status === "active" ? "inactive" : "active";
    await api.patch(`/api/v1/admin/providers/${provider.id}`, { status: next });
    load();
  }

  function startEdit(provider: Provider) {
    setEditingId(provider.id);
    setConfirmDeleteId(null);
    setDeleteBlocked(null);
    setDraft({
      name: provider.name,
      provider_type: provider.provider_type,
      integration_mode: provider.integration_mode,
      status: provider.status,
      supports_quote: provider.supports_quote,
      supports_policy: provider.supports_policy,
      supports_payment: provider.supports_payment,
      supports_documents: provider.supports_documents,
      supports_claims: provider.supports_claims,
      supports_renewal: provider.supports_renewal,
      supports_webhooks: provider.supports_webhooks,
    });
  }

  async function saveEdit(providerId: string) {
    setError(null);
    try {
      await api.patch(`/api/v1/admin/providers/${providerId}`, draft);
      setEditingId(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save changes");
    }
  }

  function closeDeleteModal() {
    if (forceBusy) return;
    setConfirmDeleteId(null);
    setDeleteBlocked(null);
    setForceDeleteId(null);
    setForceConfirmText("");
  }

  async function handleDelete(providerId: string) {
    setError(null);
    setDeleteBlocked(null);
    try {
      await api.del(`/api/v1/admin/providers/${providerId}`);
      setConfirmDeleteId(null);
      await load();
    } catch (e) {
      // A 409 here means this provider has real quote/policy history -
      // surface that reason directly rather than a generic failure, since
      // "deactivate instead" is the actual next step for the admin.
      setDeleteBlocked(e instanceof Error ? e.message : "Could not delete this provider");
    }
  }

  async function handleForceDelete(provider: Provider) {
    if (forceConfirmText !== provider.name) return;
    setForceBusy(true);
    setError(null);
    try {
      const result = await api.del<{ deleted_provider: string; deleted: Record<string, number> }>(
        `/api/v1/admin/providers/${provider.id}/force?confirm=${encodeURIComponent(forceConfirmText)}`
      );
      const summary = Object.entries(result.deleted)
        .filter(([, n]) => n > 0)
        .map(([k, n]) => `${n} ${k.replace(/_/g, " ")}`)
        .join(", ");
      setForceResult(`Deleted "${result.deleted_provider}"${summary ? ` and ${summary}` : ""}.`);
      setForceDeleteId(null);
      setForceConfirmText("");
      setConfirmDeleteId(null);
      setDeleteBlocked(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not force-delete this provider");
    } finally {
      setForceBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <h1 className="text-2xl font-bold">Insurance providers</h1>
      <p className="mt-1 text-ink-soft">
        Manage insurers and brokers integrated on SomoSure. 
      </p>

      {error && <div className="mt-4 rounded-control bg-status-error/10 px-4 py-3 text-sm text-status-error">{error}</div>}
      {forceResult && <div className="mt-4 rounded-control bg-status-success/10 px-4 py-3 text-sm text-status-success">{forceResult}</div>}

      <Card className="mt-6 flex items-end gap-3">
        <div className="flex-1">
          <Input label="Add a provider" placeholder="e.g. Britam" value={newName} onChange={(e) => setNewName(e.target.value)} />
        </div>
        <Button onClick={handleCreate} disabled={creating}>
          {creating ? "Adding…" : "Add provider"}
        </Button>
      </Card>

      <div className="mt-6 flex flex-col gap-3">
        {loading && <p className="text-ink-soft">Loading providers…</p>}
        {!loading &&
          providers.map((p) => (
            <Card key={p.id} className="flex flex-col gap-3">
              {editingId === p.id ? (
                <div className="flex flex-col gap-3">
                  <div className="grid gap-3 sm:grid-cols-3">
                    <Input label="Name" value={draft.name ?? ""} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
                    <div className="flex flex-col gap-1.5">
                      <label className="text-sm font-medium text-ink">Provider type</label>
                      <select
                        className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm"
                        value={draft.provider_type ?? ""}
                        onChange={(e) => setDraft({ ...draft, provider_type: e.target.value })}
                      >
                        <option value="insurer">Insurer</option>
                        <option value="broker">Broker</option>
                        <option value="financier">Financier</option>
                      </select>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-sm font-medium text-ink">Integration mode</label>
                      <select
                        className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm"
                        value={draft.integration_mode ?? ""}
                        onChange={(e) => setDraft({ ...draft, integration_mode: e.target.value })}
                      >
                        <option value="mock">Mock</option>
                        <option value="rate_card">Rate card</option>
                        <option value="api">Live API</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="text-sm font-medium text-ink">Capabilities</label>
                    <div className="mt-1 flex flex-wrap gap-3">
                      {SUPPORT_FLAGS.map((flag) => (
                        <label key={flag.key} className="flex items-center gap-1.5 text-sm text-ink">
                          <input
                            type="checkbox"
                            checked={Boolean(draft[flag.key as keyof ProviderEdits])}
                            onChange={(e) => setDraft({ ...draft, [flag.key]: e.target.checked })}
                          />
                          {flag.label}
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <Button onClick={() => saveEdit(p.id)}>Save changes</Button>
                    <Button variant="ghost" onClick={() => setEditingId(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">{p.name}</h3>
                      <Badge tone={statusTone[p.status] ?? "neutral"}>{p.status}</Badge>
                      {p.integration_mode === "mock" && <Badge tone="neutral">Mock integration</Badge>}
                    </div>
                    <p className="mt-1 text-xs text-ink-soft">
                      Quote: {p.supports_quote ? "yes" : "no"} · Policy: {p.supports_policy ? "yes" : "no"} · Payment:{" "}
                      {p.supports_payment ? "yes" : "no"} · Claims: {p.supports_claims ? "yes" : "no"}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="ghost" onClick={() => startEdit(p)}>
                      Edit
                    </Button>
                    <Button variant="ghost" onClick={() => toggleStatus(p)}>
                      {p.status === "active" ? "Deactivate" : "Activate"}
                    </Button>
                    <Button
                      variant="ghost"
                      className="text-status-error"
                      onClick={() => {
                        setConfirmDeleteId(p.id);
                        setDeleteBlocked(null);
                        setForceDeleteId(null);
                        setForceConfirmText("");
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          ))}
      </div>

      {deleteTarget && (
        <Modal onClose={closeDeleteModal}>
          {forceDeleteId !== deleteTarget.id ? (
            <div className="flex flex-col gap-4">
              <div>
                <h2 className="text-lg font-semibold text-ink">Delete {deleteTarget.name}?</h2>
                <p className="mt-1 text-sm text-ink-soft">This will remove the provider from SomoSure.</p>
              </div>

              {deleteBlocked && (
                <div className="rounded-control bg-status-error/10 px-3 py-2 text-xs text-status-error">
                  <p>{deleteBlocked}</p>
                  <button
                    className="mt-2 text-left font-semibold underline"
                    onClick={() => {
                      setForceDeleteId(deleteTarget.id);
                      setForceConfirmText("");
                    }}
                  >
                    I understand - permanently delete this provider and all its history anyway
                  </button>
                </div>
              )}

              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={closeDeleteModal}>
                  Cancel
                </Button>
                <Button variant="ghost" className="text-status-error" onClick={() => handleDelete(deleteTarget.id)}>
                  Confirm delete
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3 text-xs text-status-error">
              <p className="text-sm font-semibold text-ink">
                This cannot be undone. It permanently deletes every quote, application, policy, payment, claim,
                sticker, renewal and financing record tied to <strong>{deleteTarget.name}</strong>.
              </p>
              <p className="text-sm text-ink">
                Type the provider name <strong>{deleteTarget.name}</strong> below to confirm.
              </p>
              <input
                className="rounded-control border border-neutral-border px-3 py-2 text-sm text-ink"
                placeholder={deleteTarget.name}
                value={forceConfirmText}
                onChange={(e) => setForceConfirmText(e.target.value)}
                autoFocus
              />
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setForceDeleteId(null)} disabled={forceBusy}>
                  Cancel
                </Button>
                <Button
                  variant="ghost"
                  className="border-status-error text-status-error"
                  onClick={() => handleForceDelete(deleteTarget)}
                  disabled={forceBusy || forceConfirmText !== deleteTarget.name}
                >
                  {forceBusy ? "Deleting everything…" : "Permanently delete everything"}
                </Button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </main>
  );
}
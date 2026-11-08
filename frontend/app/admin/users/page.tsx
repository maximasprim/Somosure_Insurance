"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MoreHorizontal } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { api, getTokenUserId } from "@/lib/api";

interface Role {
  id: string;
  name: string;
  description: string | null;
}

interface DeletionCheck {
  can_delete: boolean;
  reasons: string[];
  blockers: { label: string; count: number; kind: string }[];
  removes_customer_profile: boolean;
}

interface StaffUser {
  id: string;
  email: string;
  phone: string | null;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  must_change_password?: boolean;
}

const selectClass =
  "rounded-control border border-neutral-border bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-deep/40 focus:border-brand-deep";

const menuItemClass =
  "block w-full px-4 py-2 text-left text-sm font-medium text-ink hover:bg-neutral focus:bg-neutral focus:outline-none";

// A readable random password (no look-alike characters) an admin can hand over.
function generatePassword(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";
  const bytes = new Uint8Array(14);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => chars[b % chars.length]).join("");
}

export default function AdminUsersPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [users, setUsers] = useState<StaffUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const myId = getTokenUserId();

  const [form, setForm] = useState({ full_name: "", email: "", phone: "", password: "", role: "", require_change: true });
  const [creating, setCreating] = useState(false);

  // One dialog at a time: edit details, reset password, or confirm "sign out everywhere".
  const [dialog, setDialog] = useState<{ kind: "edit" | "reset" | "signout" | "delete"; user: StaffUser } | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ full_name: "", email: "", phone: "" });
  const [resetForm, setResetForm] = useState({ password: "", reason: "", require_change: true });
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving] = useState(false);

  // Delete: first ask the server whether anything depends on the account.
  const [deleteCheck, setDeleteCheck] = useState<DeletionCheck | null>(null);
  const [deleteChecking, setDeleteChecking] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState("");
  const [deleteReason, setDeleteReason] = useState("");

  // The "..." actions menu: one open at a time, closed by Esc or a click anywhere else.
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [menuUp, setMenuUp] = useState(false); // open upwards when there is no room below
  useEffect(() => {
    if (!menuFor) return;
    const onDown = (e: MouseEvent) => {
      if (!(e.target as Element).closest("[data-user-menu]")) setMenuFor(null);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuFor(null);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuFor]);

  async function loadRoles() {
    const data = await api.get<Role[]>("/api/v1/admin/roles");
    setRoles(data);
    setForm((f) => (f.role ? f : { ...f, role: data.find((r) => r.name !== "customer")?.name ?? data[0]?.name ?? "" }));
  }

  async function loadUsers(q?: string, role?: string) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (q) params.set("search", q);
      if (role) params.set("role", role);
      const qs = params.toString();
      const data = await api.get<StaffUser[]>(`/api/v1/admin/users${qs ? `?${qs}` : ""}`);
      setUsers(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRoles();
    loadUsers();
  }, []);

  async function handleCreate() {
    if (!form.full_name.trim() || !form.email.trim() || !form.password.trim() || !form.role) return;
    setCreating(true);
    setError(null);
    setNotice(null);
    try {
      await api.post("/api/v1/admin/users", {
        full_name: form.full_name,
        email: form.email,
        phone: form.phone || null,
        password: form.password,
        role: form.role,
        require_password_change: form.require_change,
      });
      setForm((f) => ({ full_name: "", email: "", phone: "", password: "", role: f.role, require_change: true }));
      loadUsers(search, roleFilter);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create user");
    } finally {
      setCreating(false);
    }
  }

  async function handleRoleChange(user: StaffUser, role: string) {
    setNotice(null);
    try {
      await api.patch(`/api/v1/admin/users/${user.id}`, { role });
      loadUsers(search, roleFilter);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update role");
    }
  }

  async function handleToggleActive(user: StaffUser) {
    setNotice(null);
    try {
      await api.patch(`/api/v1/admin/users/${user.id}`, { is_active: !user.is_active });
      if (user.is_active) setNotice(`${user.full_name} was deactivated and signed out of every device.`);
      loadUsers(search, roleFilter);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update user");
    }
  }

  function closeDialog() {
    setDialog(null);
    setModalError(null);
    setSaving(false);
  }

  function openEdit(user: StaffUser) {
    setEditForm({ full_name: user.full_name, email: user.email, phone: user.phone ?? "" });
    setModalError(null);
    setNotice(null);
    setDialog({ kind: "edit", user });
  }

  function openReset(user: StaffUser) {
    setResetForm({ password: "", reason: "", require_change: true });
    setShowPassword(false);
    setModalError(null);
    setNotice(null);
    setDialog({ kind: "reset", user });
  }

  function openSignOut(user: StaffUser) {
    setModalError(null);
    setNotice(null);
    setDialog({ kind: "signout", user });
  }

  async function openDelete(user: StaffUser) {
    setDeleteCheck(null);
    setConfirmEmail("");
    setDeleteReason("");
    setModalError(null);
    setNotice(null);
    setDeleteChecking(true);
    setDialog({ kind: "delete", user });
    try {
      setDeleteCheck(await api.get<DeletionCheck>(`/api/v1/admin/users/${user.id}/deletion-check`));
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Could not check whether this account can be deleted");
    } finally {
      setDeleteChecking(false);
    }
  }

  async function handleDelete(e: React.FormEvent) {
    e.preventDefault();
    if (!dialog) return;
    const user = dialog.user;
    setSaving(true);
    setModalError(null);
    try {
      await api.del(`/api/v1/admin/users/${user.id}?confirm_email=${encodeURIComponent(confirmEmail.trim())}`, {
        reason: deleteReason || undefined,
      });
      closeDialog();
      setNotice(`${user.full_name}'s account was deleted.`);
      loadUsers(search, roleFilter);
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to delete the account");
      setSaving(false);
    }
  }

  async function handleSaveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!dialog) return;
    const user = dialog.user;
    // Send only what actually changed.
    const changes: { full_name?: string; email?: string; phone?: string | null } = {};
    if (editForm.full_name.trim() !== user.full_name) changes.full_name = editForm.full_name.trim();
    if (editForm.email.trim() !== user.email) changes.email = editForm.email.trim();
    if (editForm.phone.trim() !== (user.phone ?? "")) changes.phone = editForm.phone.trim() || null;
    if (Object.keys(changes).length === 0) {
      closeDialog();
      return;
    }
    setSaving(true);
    setModalError(null);
    try {
      await api.patch(`/api/v1/admin/users/${user.id}`, changes);
      closeDialog();
      setNotice(`Details updated for ${editForm.full_name.trim() || user.full_name}.`);
      loadUsers(search, roleFilter);
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to update details");
      setSaving(false);
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    if (!dialog) return;
    const user = dialog.user;
    if (resetForm.password.length < 8) {
      setModalError("The new password must be at least 8 characters.");
      return;
    }
    setSaving(true);
    setModalError(null);
    try {
      await api.post(
        `/api/v1/admin/users/${user.id}/reset-password`,
        { new_password: resetForm.password, require_password_change: resetForm.require_change },
        { reason: resetForm.reason || undefined }
      );
      closeDialog();
      setNotice(
        `Password changed for ${user.full_name} and they were signed out of every device.` +
          (resetForm.require_change ? " They must choose their own password at next sign-in." : "") +
          " Share the new password with them securely."
      );
      loadUsers(search, roleFilter);
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to reset password");
      setSaving(false);
    }
  }

  async function handleRevokeSessions() {
    if (!dialog) return;
    const user = dialog.user;
    setSaving(true);
    setModalError(null);
    try {
      await api.post(`/api/v1/admin/users/${user.id}/revoke-sessions`);
      closeDialog();
      setNotice(`${user.full_name} was signed out of every device.`);
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to sign the user out");
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto max-w-8xl px-3 py-4 pb-40">
      <h1 className="text-2xl font-bold">Users & access</h1>
      <p className="mt-1 text-ink-soft">
        Invite staff accounts, edit anyone&apos;s details, reset passwords and control who has which role.
      </p>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}
      {notice && <p className="mt-4 rounded-control bg-neutral px-4 py-2 text-sm text-ink">{notice}</p>}

      <Card className="mt-6 flex flex-col gap-3">
        <h2 className="font-semibold">Invite a staff account</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label="Full name"
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
          <Input
            label="Email"
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
          <Input
            label="Phone (optional)"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
          />
          <Input
            label="Temporary password"
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-ink">Role</label>
            <select className={selectClass} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {roles.map((r) => (
                <option key={r.id} value={r.name}>
                  {r.name.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={form.require_change}
            onChange={(e) => setForm({ ...form, require_change: e.target.checked })}
          />
          Make them choose their own password at first sign-in
        </label>
        <div>
          <Button onClick={handleCreate} disabled={creating}>
            {creating ? "Inviting…" : "Invite"}
          </Button>
        </div>
      </Card>

      <div className="mt-8 flex flex-wrap items-end gap-3">
        <div className="flex-1">
          <Input
            label="Search by name, email or phone"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadUsers(search, roleFilter)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-ink">Role</label>
          <select
            className={selectClass}
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value);
              loadUsers(search, e.target.value);
            }}
          >
            <option value="">All roles</option>
            {roles.map((r) => (
              <option key={r.id} value={r.name}>
                {r.name.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
        <Button variant="ghost" onClick={() => loadUsers(search, roleFilter)}>
          Search
        </Button>
      </div>

      <div className="mt-4 flex flex-col gap-3">
        {loading && <p className="text-ink-soft">Loading…</p>}
        {!loading && users.length === 0 && <p className="text-ink-soft">No users found.</p>}
        {!loading &&
          users.map((u) => {
            const isSelf = myId === u.id;
            return (
              <Card key={u.id} className="flex flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">{u.full_name}</h3>
                      {!u.is_active && <Badge tone="error">Deactivated</Badge>}
                      {u.must_change_password && <Badge tone="info">Must change password</Badge>}
                      {isSelf && <Badge tone="brand">You</Badge>}
                    </div>
                    <p className="mt-1 text-xs text-ink-soft">
                      {u.email}
                      {u.phone ? ` · ${u.phone}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      className={selectClass}
                      value={u.role}
                      disabled={isSelf}
                      onChange={(e) => handleRoleChange(u, e.target.value)}
                    >
                      {roles.map((r) => (
                        <option key={r.id} value={r.name}>
                          {r.name.replace(/_/g, " ")}
                        </option>
                      ))}
                      {!roles.some((r) => r.name === u.role) && <option value={u.role}>{u.role}</option>}
                    </select>
                    <div className="relative" data-user-menu>
                      <button
                        type="button"
                        aria-label={`Actions for ${u.full_name}`}
                        aria-haspopup="menu"
                        aria-expanded={menuFor === u.id}
                        onClick={(e) => {
                          const rect = e.currentTarget.getBoundingClientRect();
                          setMenuUp(window.innerHeight - rect.bottom < 300);
                          setMenuFor(menuFor === u.id ? null : u.id);
                        }}
                        className="rounded-control border border-neutral-border p-2 text-ink hover:bg-neutral"
                      >
                        <MoreHorizontal className="h-5 w-5" />
                      </button>
                      {menuFor === u.id && (
                        <div
                          role="menu"
                          className={`absolute right-0 z-20 w-56 rounded-control border border-neutral-border bg-white py-1 shadow-card ${
                            menuUp ? "bottom-full mb-1" : "top-full mt-1"
                          }`}
                        >
                          <button
                            role="menuitem"
                            className={menuItemClass}
                            onClick={() => {
                              setMenuFor(null);
                              openEdit(u);
                            }}
                          >
                            Edit details
                          </button>
                          {isSelf ? (
                            <Link role="menuitem" href="/change-password" className={menuItemClass}>
                              Change my password
                            </Link>
                          ) : (
                            <>
                              <button
                                role="menuitem"
                                className={menuItemClass}
                                onClick={() => {
                                  setMenuFor(null);
                                  openReset(u);
                                }}
                              >
                                Reset password
                              </button>
                              <button
                                role="menuitem"
                                className={menuItemClass}
                                onClick={() => {
                                  setMenuFor(null);
                                  openSignOut(u);
                                }}
                              >
                                Sign out everywhere
                              </button>
                              <div className="my-1 border-t border-neutral-border" />
                              <button
                                role="menuitem"
                                className={`${menuItemClass} ${u.is_active ? "text-status-error" : ""}`}
                                onClick={() => {
                                  setMenuFor(null);
                                  handleToggleActive(u);
                                }}
                              >
                                {u.is_active ? "Deactivate" : "Activate"}
                              </button>
                              <button
                                role="menuitem"
                                className={`${menuItemClass} text-status-error`}
                                onClick={() => {
                                  setMenuFor(null);
                                  openDelete(u);
                                }}
                              >
                                Delete…
                              </button>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
      </div>

      {/* Edit details */}
      <Modal
        open={dialog?.kind === "edit"}
        onClose={closeDialog}
        title="Edit details"
        description={dialog ? `Update ${dialog.user.full_name}'s account details.` : undefined}
      >
        <form onSubmit={handleSaveEdit} className="flex flex-col gap-4">
          <Input
            label="Full name"
            autoFocus
            value={editForm.full_name}
            onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
          />
          <Input
            label="Email"
            type="email"
            value={editForm.email}
            onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
          />
          <Input
            label="Phone"
            value={editForm.phone}
            onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
          />
          <p className="text-xs text-ink-soft">
            Changing the email changes what they sign in with. Their customer profile is updated to match.
          </p>
          {modalError && <p className="text-sm text-status-error">{modalError}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={closeDialog}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Reset password */}
      <Modal
        open={dialog?.kind === "reset"}
        onClose={closeDialog}
        title="Reset password"
        description={dialog ? `Set a new password for ${dialog.user.full_name}. They'll be signed out of every device.` : undefined}
      >
        <form onSubmit={handleResetPassword} className="flex flex-col gap-4">
          <Input
            label="New password (min. 8 characters)"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            autoFocus
            value={resetForm.password}
            onChange={(e) => setResetForm({ ...resetForm, password: e.target.value })}
          />
          <div className="-mt-2 flex gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setResetForm({ ...resetForm, password: generatePassword() });
                setShowPassword(true);
              }}
            >
              Generate one
            </Button>
            <Button type="button" variant="ghost" onClick={() => setShowPassword((v) => !v)}>
              {showPassword ? "Hide" : "Show"}
            </Button>
          </div>
          <Input
            label="Reason (optional, kept in the audit trail)"
            value={resetForm.reason}
            onChange={(e) => setResetForm({ ...resetForm, reason: e.target.value })}
          />
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={resetForm.require_change}
              onChange={(e) => setResetForm({ ...resetForm, require_change: e.target.checked })}
            />
            Make them choose their own password at next sign-in
          </label>
          <p className="text-xs text-ink-soft">
            The password is never stored in the audit trail, and any password-reset email link they already requested
            stops working.
          </p>
          {modalError && <p className="text-sm text-status-error">{modalError}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={closeDialog}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Set new password"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Sign out everywhere */}
      <Modal
        open={dialog?.kind === "signout"}
        onClose={closeDialog}
        title="Sign out everywhere?"
        description={
          dialog
            ? `${dialog.user.full_name} will be signed out of every device. They can sign straight back in with their current password.`
            : undefined
        }
      >
        {modalError && <p className="mb-4 text-sm text-status-error">{modalError}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={closeDialog}>
            Cancel
          </Button>
          <Button type="button" onClick={handleRevokeSessions} disabled={saving}>
            {saving ? "Signing out…" : "Sign out"}
          </Button>
        </div>
      </Modal>

      {/* Delete */}
      <Modal
        open={dialog?.kind === "delete"}
        onClose={closeDialog}
        title="Delete account"
        description={dialog ? `${dialog.user.full_name} · ${dialog.user.email}` : undefined}
      >
        {deleteChecking && <p className="text-sm text-ink-soft">Checking what depends on this account…</p>}
        {modalError && !deleteCheck && <p className="text-sm text-status-error">{modalError}</p>}

        {deleteCheck && !deleteCheck.can_delete && dialog && (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-ink">This account can&apos;t be deleted.</p>
            <ul className="flex flex-col gap-1 text-sm text-ink-soft">
              {deleteCheck.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
              {deleteCheck.blockers.map((b) => (
                <li key={`${b.kind}-${b.label}`}>
                  {b.count} {b.label}
                </li>
              ))}
            </ul>
            {deleteCheck.blockers.length > 0 && (
              <p className="text-xs text-ink-soft">
                These records have to be kept. Deactivating the account signs the user out and blocks sign-in while
                keeping everything intact.
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={closeDialog}>
                Close
              </Button>
              {dialog.user.is_active && deleteCheck.blockers.length > 0 && (
                <Button
                  type="button"
                  onClick={() => {
                    const user = dialog.user;
                    closeDialog();
                    handleToggleActive(user);
                  }}
                >
                  Deactivate instead
                </Button>
              )}
            </div>
          </div>
        )}

        {deleteCheck && deleteCheck.can_delete && dialog && (
          <form onSubmit={handleDelete} className="flex flex-col gap-4">
            <p className="text-sm text-ink">
              This permanently deletes the account
              {deleteCheck.removes_customer_profile ? " and its (unused) customer profile" : ""}. It can&apos;t be
              undone. Nothing else in the system depends on it.
            </p>
            <Input
              label={`Type ${dialog.user.email} to confirm`}
              autoFocus
              value={confirmEmail}
              onChange={(e) => setConfirmEmail(e.target.value)}
            />
            <Input
              label="Reason (optional, kept in the audit trail)"
              value={deleteReason}
              onChange={(e) => setDeleteReason(e.target.value)}
            />
            {modalError && <p className="text-sm text-status-error">{modalError}</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={closeDialog}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={saving || confirmEmail.trim().toLowerCase() !== dialog.user.email.toLowerCase()}
              >
                {saving ? "Deleting…" : "Delete account"}
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </main>
  );
}
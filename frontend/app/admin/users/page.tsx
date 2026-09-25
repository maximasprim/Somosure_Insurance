"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api, getTokenUserId } from "@/lib/api";

interface Role {
  id: string;
  name: string;
  description: string | null;
}

interface StaffUser {
  id: string;
  email: string;
  phone: string | null;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const selectClass =
  "rounded-control border border-neutral-border bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-deep/40 focus:border-brand-deep";

export default function AdminUsersPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [users, setUsers] = useState<StaffUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const myId = getTokenUserId();

  const [form, setForm] = useState({ full_name: "", email: "", phone: "", password: "", role: "" });
  const [creating, setCreating] = useState(false);

  async function loadRoles() {
    const data = await api.get<Role[]>("/api/v1/admin/roles");
    setRoles(data);
    setForm((f) => (f.role ? f : { ...f, role: data.find((r) => r.name !== "customer")?.name ?? data[0]?.name ?? "" }));
  }

  async function loadUsers(q?: string) {
    setLoading(true);
    setError(null);
    try {
      const query = q ? `?search=${encodeURIComponent(q)}` : "";
      const data = await api.get<StaffUser[]>(`/api/v1/admin/users${query}`);
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
    try {
      await api.post("/api/v1/admin/users", {
        full_name: form.full_name,
        email: form.email,
        phone: form.phone || null,
        password: form.password,
        role: form.role,
      });
      setForm((f) => ({ full_name: "", email: "", phone: "", password: "", role: f.role }));
      loadUsers(search);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create user");
    } finally {
      setCreating(false);
    }
  }

  async function handleRoleChange(user: StaffUser, role: string) {
    try {
      await api.patch(`/api/v1/admin/users/${user.id}`, { role });
      loadUsers(search);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update role");
    }
  }

  async function handleToggleActive(user: StaffUser) {
    try {
      await api.patch(`/api/v1/admin/users/${user.id}`, { is_active: !user.is_active });
      loadUsers(search);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update user");
    }
  }

  return (
    <main className="mx-auto max-w-8xl px-6 py-12">
      <h1 className="text-2xl font-bold">Staff & access</h1>
      <p className="mt-1 text-ink-soft">
        Invite staff accounts and control who has which role. This is the only place roles can be changed - there's
        no other way to grant admin access.
      </p>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

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
        <div>
          <Button onClick={handleCreate} disabled={creating}>
            {creating ? "Inviting…" : "Invite"}
          </Button>
        </div>
      </Card>

      <div className="mt-8 flex items-end gap-3">
        <div className="flex-1">
          <Input
            label="Search by name or email"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadUsers(search)}
          />
        </div>
        <Button variant="ghost" onClick={() => loadUsers(search)}>
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
              <Card key={u.id} className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{u.full_name}</h3>
                    {!u.is_active && <Badge tone="error">Deactivated</Badge>}
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
                  <Button variant="ghost" onClick={() => handleToggleActive(u)} disabled={isSelf}>
                    {u.is_active ? "Deactivate" : "Activate"}
                  </Button>
                </div>
              </Card>
            );
          })}
      </div>
    </main>
  );
}

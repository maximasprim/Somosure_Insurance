"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api, getTokenUserId } from "@/lib/api";

interface StaffUser {
  id: string;
  full_name: string;
}

interface Task {
  id: string;
  title: string;
  lead_id: string | null;
  assigned_to_user_id: string | null;
  assigned_to_name: string | null;
  due_at: string | null;
  status: string;
}

const selectClass =
  "rounded-control border border-neutral-border bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-deep/40 focus:border-brand-deep";

export default function AdminTasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [staff, setStaff] = useState<StaffUser[]>([]);
  const [statusFilter, setStatusFilter] = useState<"open" | "done" | "">("open");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ title: "", assigned_to_user_id: "", due_at: "" });
  const [creating, setCreating] = useState(false);
  const myId = getTokenUserId();

  async function loadStaff() {
    try {
      setStaff(await api.get<StaffUser[]>("/api/v1/admin/users"));
    } catch {
      // Staff picker is a convenience, not required - fall back to unassigned-only if this 403s for the viewer's role.
    }
  }

  async function loadTasks() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      setTasks(await api.get<Task[]>(`/api/v1/admin/tasks?${params.toString()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStaff();
  }, []);

  useEffect(() => {
    loadTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function handleCreate() {
    if (!form.title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await api.post("/api/v1/admin/tasks", {
        title: form.title,
        assigned_to_user_id: form.assigned_to_user_id || myId || null,
        due_at: form.due_at ? new Date(form.due_at).toISOString() : null,
      });
      setForm({ title: "", assigned_to_user_id: "", due_at: "" });
      loadTasks();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create task");
    } finally {
      setCreating(false);
    }
  }

  async function toggleDone(t: Task) {
    await api.patch(`/api/v1/admin/tasks/${t.id}`, { status: t.status === "done" ? "open" : "done" });
    loadTasks();
  }

  return (
    <main className="mx-auto max-w-8xl px-3 py-4">
      <h1 className="text-2xl font-bold">Tasks</h1>
      <p className="mt-1 text-ink-soft">Follow-ups and to-dos for the team - optionally tied to a lead.</p>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      <Card className="mt-6 flex flex-col gap-3">
        <h2 className="font-semibold">New task</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <Input label="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-ink">Assign to</label>
            <select
              className={selectClass}
              value={form.assigned_to_user_id}
              onChange={(e) => setForm({ ...form, assigned_to_user_id: e.target.value })}
            >
              <option value="">Myself</option>
              {staff.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name}
                </option>
              ))}
            </select>
          </div>
          <Input
            label="Due"
            type="datetime-local"
            value={form.due_at}
            onChange={(e) => setForm({ ...form, due_at: e.target.value })}
          />
        </div>
        <div>
          <Button onClick={handleCreate} disabled={creating}>
            {creating ? "Adding…" : "Add task"}
          </Button>
        </div>
      </Card>

      <div className="mt-6 flex gap-2">
        {(["open", "done", ""] as const).map((s) => (
          <Button key={s || "all"} variant={statusFilter === s ? "primary" : "ghost"} onClick={() => setStatusFilter(s)}>
            {s === "" ? "All" : s === "open" ? "Open" : "Done"}
          </Button>
        ))}
      </div>

      <div className="mt-4 flex flex-col gap-2">
        {loading && <p className="text-ink-soft">Loading…</p>}
        {!loading && tasks.length === 0 && <p className="text-ink-soft">No tasks found.</p>}
        {!loading &&
          tasks.map((t) => (
            <Card key={t.id} className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className={t.status === "done" ? "font-semibold line-through text-ink-soft" : "font-semibold"}>{t.title}</h3>
                  {t.status === "done" && <Badge tone="success">Done</Badge>}
                </div>
                <p className="mt-1 text-xs text-ink-soft">
                  {t.assigned_to_name ?? "Unassigned"}
                  {t.due_at ? ` · due ${new Date(t.due_at).toLocaleString("en-KE")}` : ""}
                </p>
              </div>
              <Button variant="ghost" onClick={() => toggleDone(t)}>
                {t.status === "done" ? "Reopen" : "Mark done"}
              </Button>
            </Card>
          ))}
      </div>
    </main>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api, clearSession, getTokenRole, hasValidSession, mustChangePassword, storeSession } from "@/lib/api";

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  must_change_password?: boolean;
}

const STAFF_ROLES = ["super_admin", "operations", "management", "underwriter", "claims_officer", "finance_officer"];

export default function ChangePasswordPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [forced, setForced] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasValidSession()) {
      router.replace("/login");
      return;
    }
    setForced(mustChangePassword());
    setReady(true);
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (next.length < 8) {
      setError("The new password must be at least 8 characters.");
      return;
    }
    if (next !== confirm) {
      setError("Those passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      // Other devices are signed out by this; the response keeps this one signed in.
      const res = await api.post<TokenResponse>("/api/v1/auth/change-password", {
        current_password: current,
        new_password: next,
      });
      storeSession(res.access_token, res.refresh_token);
      const role = getTokenRole();
      router.push(role && STAFF_ROLES.includes(role) ? "/admin" : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change your password");
    } finally {
      setBusy(false);
    }
  }

  function handleLogout() {
    clearSession();
    router.replace("/login");
  }

  if (!ready) return null;

  return (
    <main className="flex min-h-screen flex-col">
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
        <Card>
          <h1 className="text-xl font-bold">{forced ? "Choose a new password" : "Change password"}</h1>
          <p className="mt-1 text-sm text-ink-soft">
            {forced
              ? "An administrator set a temporary password for your account. Choose your own to continue."
              : "You'll stay signed in here; your other devices will be signed out."}
          </p>
          <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
            <Input
              label={forced ? "Temporary password" : "Current password"}
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              required
            />
            <Input
              label="New password (min. 8 characters)"
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              required
            />
            <Input
              label="Confirm new password"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
            {error && <p className="text-sm text-status-error">{error}</p>}
            <Button type="submit" disabled={busy} size="lg">
              {busy ? "Saving…" : "Save new password"}
            </Button>
            {forced ? (
              <button type="button" onClick={handleLogout} className="text-sm font-medium text-ink-soft hover:text-ink">
                Log out
              </button>
            ) : (
              <button
                type="button"
                onClick={() => router.back()}
                className="text-sm font-medium text-ink-soft hover:text-ink"
              >
                Cancel
              </button>
            )}
          </form>
        </Card>
      </div>
    </main>
  );
}

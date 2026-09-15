"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api, storeSession, getTokenRole } from "@/lib/api";

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<TokenResponse>("/api/v1/auth/login", { email, password });
      storeSession(res.access_token, res.refresh_token);
      const role = getTokenRole();
      const staffRoles = ["super_admin", "operations", "management", "underwriter", "claims_officer", "finance_officer"];
      router.push(role && staffRoles.includes(role) ? "/admin/applications" : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-md flex-col justify-center px-6 py-24">
      <Card>
        <h1 className="text-xl font-bold">Log in</h1>
        <p className="mt-1 text-sm text-ink-soft">Staff and customer accounts use the same login.</p>
        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <p className="text-sm text-status-error">{error}</p>}
          <Button type="submit" disabled={busy} size="lg">
            {busy ? "Logging in…" : "Log in"}
          </Button>
        </form>
      </Card>
    </main>
  );
}

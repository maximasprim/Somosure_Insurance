"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { AuthTopbar } from "@/components/AuthTopbar";
import { api, storeSession } from "@/lib/api";

interface TokenResponse {
  access_token: string;
  refresh_token: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ full_name: "", email: "", phone: "", password: "", referral_code: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/auth/register", form);
      const res = await api.post<TokenResponse>("/api/v1/auth/login", { email: form.email, password: form.password });
      storeSession(res.access_token, res.refresh_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create your account");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col">
      <AuthTopbar crossLinkHref="/login" crossLinkLabel="Log in instead" />
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-2">
        <Card>
          <h1 className="text-xl font-bold">Create your account</h1>
          <p className="mt-1 text-sm text-ink-soft">Manage your policies, payments, and claims in one place.</p>
          <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
            <Input label="Full name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
            <Input label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            <Input label="Phone" placeholder="07XX XXX XXX" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            <Input
              label="Password"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
              minLength={8}
            />
            <Input
              label="Referral code (optional)"
              value={form.referral_code}
              onChange={(e) => setForm({ ...form, referral_code: e.target.value })}
            />
            {error && <p className="text-sm text-status-error">{error}</p>}
            <Button type="submit" disabled={busy} size="lg">
              {busy ? "Creating account…" : "Create account"}
            </Button>
          </form>
        </Card>
      </div>
    </main>
  );
}

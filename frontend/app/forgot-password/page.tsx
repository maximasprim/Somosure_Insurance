"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { AuthTopbar } from "@/components/AuthTopbar";
import { api } from "@/lib/api";

interface ForgotPasswordResponse {
  message: string;
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // The backend always returns the same generic message whether or
      // not the email is registered - by design, so this form can't be
      // used to check which emails have an account.
      const res = await api.post<ForgotPasswordResponse>("/api/v1/auth/forgot-password", { email });
      setMessage(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong - please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col">
      <AuthTopbar crossLinkHref="/login" crossLinkLabel="Back to log in" />
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
        <Card>
          <h1 className="text-xl font-bold">Reset your password</h1>
          <p className="mt-1 text-sm text-ink-soft">
            Enter the email on your account and we'll send you a link to set a new password.
          </p>

          {message ? (
            <p className="mt-6 rounded-control bg-brand-tint px-4 py-3 text-sm text-ink">{message}</p>
          ) : (
            <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
              <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              {error && <p className="text-sm text-status-error">{error}</p>}
              <Button type="submit" disabled={busy} size="lg">
                {busy ? "Sending…" : "Send reset link"}
              </Button>
            </form>
          )}
        </Card>
      </div>
    </main>
  );
}

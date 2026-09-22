"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { AuthTopbar } from "@/components/AuthTopbar";
import { api } from "@/lib/api";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Those passwords don't match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/auth/reset-password", { token, new_password: password });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That reset link is invalid or has expired.");
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <Card>
        <h1 className="text-xl font-bold">Invalid reset link</h1>
        <p className="mt-2 text-sm text-ink-soft">
          This link is missing its reset token. Request a new one from the{" "}
          <Link href="/forgot-password" className="font-medium text-ink underline">
            forgot password
          </Link>{" "}
          page.
        </p>
      </Card>
    );
  }

  if (done) {
    return (
      <Card>
        <h1 className="text-xl font-bold">Password updated</h1>
        <p className="mt-2 text-sm text-ink-soft">You can now log in with your new password.</p>
        <Link href="/login" className="mt-4 block">
          <Button size="lg" className="w-full">Log in</Button>
        </Link>
      </Card>
    );
  }

  return (
    <Card>
      <h1 className="text-xl font-bold">Set a new password</h1>
      <p className="mt-1 text-sm text-ink-soft">Choose a new password for your account.</p>
      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <Input
          label="New password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={8}
          required
        />
        <Input
          label="Confirm new password"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          minLength={8}
          required
        />
        {error && <p className="text-sm text-status-error">{error}</p>}
        <Button type="submit" disabled={busy} size="lg">
          {busy ? "Saving…" : "Set new password"}
        </Button>
      </form>
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="flex min-h-screen flex-col">
      <AuthTopbar crossLinkHref="/login" crossLinkLabel="Back to log in" />
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
        <Suspense fallback={<p className="text-center text-ink-soft">Loading…</p>}>
          <ResetPasswordForm />
        </Suspense>
      </div>
    </main>
  );
}

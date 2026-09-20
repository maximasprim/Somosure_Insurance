"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api, isLoggedIn } from "@/lib/api";
import type { CustomerProfile } from "@/lib/types";

export default function ProfilePage() {
  const [profile, setProfile] = useState<CustomerProfile | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      window.location.href = "/login";
      return;
    }
    api.get<CustomerProfile>("/api/v1/me").then(setProfile).catch((e) => setError(e.message));
  }, []);

  async function handleSave() {
    if (!profile) return;
    setError(null);
    setSaved(false);
    try {
      const updated = await api.patch<CustomerProfile>("/api/v1/me", {
        full_name: profile.full_name,
        phone: profile.phone,
        id_number: profile.id_number,
        kra_pin: profile.kra_pin,
      });
      setProfile(updated);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save changes");
    }
  }

  if (!profile) return <main className="mx-auto max-w-lg px-6 py-12 text-ink-soft">Loading…</main>;

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <h1 className="text-2xl font-bold">My profile</h1>
      <Card className="mt-6 flex flex-col gap-4">
        <Input label="Full name" value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} />
        <Input label="Email" value={profile.email ?? ""} disabled />
        <Input label="Phone" value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} />
        <Input label="National ID" value={profile.id_number ?? ""} onChange={(e) => setProfile({ ...profile, id_number: e.target.value })} />
        <Input label="KRA PIN" value={profile.kra_pin ?? ""} onChange={(e) => setProfile({ ...profile, kra_pin: e.target.value })} />
        {error && <p className="text-sm text-status-error">{error}</p>}
        {saved && <p className="text-sm text-status-success">Saved.</p>}
        <Button onClick={handleSave}>Save changes</Button>
      </Card>
    </main>
  );
}

"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Mail, MapPin, Phone } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { WhatsAppButton } from "@/components/WhatsAppButton";
import { Reveal } from "@/components/Reveal";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

export default function ContactPage() {
  const [form, setForm] = useState({ full_name: "", phone: "", email: "", message: "" });
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/contact", form);
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send your message - try WhatsApp instead.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <Navbar />
      <section className="mx-auto grid max-w-5xl gap-10 px-6 py-16 md:grid-cols-2 md:px-12">
        <Reveal direction="left">
          <h1 className="text-3xl font-extrabold md:text-4xl">Talk to us</h1>
          <p className="mt-3 max-w-prose text-ink-soft">
            Questions about a quote, a claim, or which cover fits you? Send a message and an advisor will follow up -
            or reach us directly below.
          </p>
          <div className="mt-8 flex flex-col gap-4 text-sm">
            <div className="flex items-center gap-3"><Phone className="h-5 w-5 text-brand-deep" /> +254 700 000 000</div>
            <div className="flex items-center gap-3"><Mail className="h-5 w-5 text-brand-deep" /> hello@somosure.co.ke</div>
            <div className="flex items-center gap-3"><MapPin className="h-5 w-5 text-brand-deep" /> Nairobi, Kenya</div>
          </div>
        </Reveal>

        <Reveal direction="right" delay={0.1}>
          <Card>
            {sent ? (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="py-8 text-center">
                <h2 className="text-lg font-bold">Message sent</h2>
                <p className="mt-2 text-sm text-ink-soft">We'll get back to you shortly.</p>
              </motion.div>
            ) : (
              <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                <Input label="Full name" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
                <Input label="Phone" required placeholder="07XX XXX XXX" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                <Input label="Email (optional)" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-ink">Message</label>
                  <textarea
                    required
                    rows={4}
                    value={form.message}
                    onChange={(e) => setForm({ ...form, message: e.target.value })}
                    className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm"
                  />
                </div>
                {error && <p className="text-sm text-status-error">{error}</p>}
                <Button type="submit" disabled={busy}>{busy ? "Sending…" : "Send message"}</Button>
              </form>
            )}
          </Card>
        </Reveal>
      </section>
      <Footer />
      <WhatsAppButton />
    </main>
  );
}

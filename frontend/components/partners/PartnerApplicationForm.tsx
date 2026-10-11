"use client";

import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

export const PARTNER_TYPES: { value: string; label: string }[] = [
  { value: "car_dealer", label: "Car dealer" },
  { value: "vehicle_importer", label: "Vehicle importer" },
  { value: "employer", label: "Employer" },
  { value: "sme", label: "Small business (SME)" },
  { value: "bank", label: "Bank" },
  { value: "sacco", label: "SACCO" },
  { value: "agent", label: "Agent" },
  { value: "corporate", label: "Corporate" },
];

const MODELS = [
  { value: "referrals", label: "Refer our customers to Somosure" },
  { value: "applications", label: "Submit insurance applications for our customers" },
  { value: "both", label: "Both" },
];
const VOLUMES = ["1-10", "11-50", "51-200", "200+"];
const PRODUCTS = [
  { value: "motor", label: "Motor" },
  { value: "medical", label: "Medical" },
  { value: "life", label: "Life" },
  { value: "property", label: "Property" },
  { value: "travel", label: "Travel" },
  { value: "personal_accident", label: "Personal accident" },
  { value: "professional_indemnity", label: "Professional indemnity" },
  { value: "wiba", label: "WIBA" },
];

const selectClass = "rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm";
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;

const empty = {
  business_name: "", partner_type: "", town: "", website: "", contact_name: "", contact_phone: "", contact_email: "",
  working_model: "", monthly_clients: "", message: "",
};

/** The "Become a partner" application. Sends nothing until every required answer is
 *  filled in, and tells the applicant plainly what happens next. */
export function PartnerApplicationForm() {
  const [form, setForm] = useState(empty);
  const [products, setProducts] = useState<string[]>([]);
  const [consent, setConsent] = useState(false);
  const [fax, setFax] = useState(""); // honeypot - real people never see this field
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reference, setReference] = useState<string | null>(null);

  const set = (key: keyof typeof empty, value: string) => setForm((f) => ({ ...f, [key]: value }));
  const toggleProduct = (value: string) =>
    setProducts((p) => (p.includes(value) ? p.filter((x) => x !== value) : [...p, value]));

  function validate(): string | null {
    if (form.business_name.trim().length < 2) return "Please enter your business name.";
    if (!form.partner_type) return "Please choose the type of business.";
    if (form.contact_name.trim().length < 2) return "Please enter the contact person's name.";
    if (form.contact_phone.replace(/\D/g, "").length < 9) return "Please enter a valid phone number.";
    if (!EMAIL.test(form.contact_email.trim())) return "Please enter a valid email address.";
    if (!form.working_model) return "Please tell us how you'd like to work with us.";
    if (!form.monthly_clients) return "Please choose roughly how many customers you could send us each month.";
    if (form.message.trim().length < 10) return "Please tell us a little more about how you'd work with us (a sentence or two).";
    if (!consent) return "Please tick the box to agree to be contacted about your application.";
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ reference: string }>("/api/v1/partner-applications", {
        ...form,
        business_name: form.business_name.trim(),
        contact_name: form.contact_name.trim(),
        contact_email: form.contact_email.trim(),
        contact_phone: form.contact_phone.trim(),
        town: form.town.trim() || null,
        website: form.website.trim() || null,
        message: form.message.trim(),
        products,
        consent,
        fax: fax || null,
      });
      setReference(res.reference);
    } catch (err) {
      setError(err instanceof Error ? err.message : "We couldn't send your application - please try again, or reach us on WhatsApp.");
    } finally {
      setBusy(false);
    }
  }

  if (reference) {
    return (
      <Card className="flex flex-col items-center gap-3 py-10 text-center">
        <CheckCircle2 className="h-10 w-10 text-status-success" aria-hidden />
        <h2 className="text-xl font-bold">Thank you - we&apos;ve got your application</h2>
        <p className="max-w-md text-sm text-ink-soft">
          Our team will review it and get in touch on the phone number or email you gave us. Your reference is{" "}
          <span className="font-mono font-bold text-ink">{reference}</span> - quote it if you contact us about this.
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <form onSubmit={submit} className="grid gap-5 sm:grid-cols-2" noValidate>
        <Input label="Business name" value={form.business_name} onChange={(e) => set("business_name", e.target.value)} />
        <div className="flex flex-col gap-1.5">
          <label htmlFor="partner-type" className="text-sm font-medium text-ink">Type of business</label>
          <select id="partner-type" value={form.partner_type} onChange={(e) => set("partner_type", e.target.value)} className={selectClass}>
            <option value="">Select…</option>
            {PARTNER_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <Input label="Town / area (optional)" value={form.town} onChange={(e) => set("town", e.target.value)} />
        <Input label="Website (optional)" placeholder="https://" value={form.website} onChange={(e) => set("website", e.target.value)} />

        <Input label="Contact person" value={form.contact_name} onChange={(e) => set("contact_name", e.target.value)} />
        <Input label="Phone" type="tel" placeholder="07XX XXX XXX" value={form.contact_phone} onChange={(e) => set("contact_phone", e.target.value)} />
        <div className="sm:col-span-2">
          <Input label="Email" type="email" value={form.contact_email} onChange={(e) => set("contact_email", e.target.value)} />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="partner-model" className="text-sm font-medium text-ink">How would you like to work with us?</label>
          <select id="partner-model" value={form.working_model} onChange={(e) => set("working_model", e.target.value)} className={selectClass}>
            <option value="">Select…</option>
            {MODELS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="partner-volume" className="text-sm font-medium text-ink">Customers you could send us each month</label>
          <select id="partner-volume" value={form.monthly_clients} onChange={(e) => set("monthly_clients", e.target.value)} className={selectClass}>
            <option value="">Select…</option>
            {VOLUMES.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>

        <fieldset className="flex flex-col gap-2 sm:col-span-2">
          <legend className="text-sm font-medium text-ink">Which insurance would you want to offer? (optional)</legend>
          <div className="flex flex-wrap gap-2">
            {PRODUCTS.map((p) => {
              const on = products.includes(p.value);
              return (
                <button
                  key={p.value}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleProduct(p.value)}
                  className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${
                    on ? "border-brand-deep bg-brand-tint text-ink" : "border-neutral-border text-ink-soft hover:border-brand-deep/50"
                  }`}
                >
                  {p.label}
                </button>
              );
            })}
          </div>
        </fieldset>

        <div className="flex flex-col gap-1.5 sm:col-span-2">
          <label htmlFor="partner-message" className="text-sm font-medium text-ink">Tell us how you&apos;d work with us</label>
          <textarea
            id="partner-message"
            rows={4}
            maxLength={2000}
            placeholder="e.g. We sell around forty used cars a month and want every buyer to leave with insurance."
            value={form.message}
            onChange={(e) => set("message", e.target.value)}
            className={selectClass}
          />
        </div>

        {/* Honeypot: hidden from people and screen readers; bots fill it in. */}
        <div aria-hidden="true" className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
          <label>Fax <input tabIndex={-1} autoComplete="off" value={fax} onChange={(e) => setFax(e.target.value)} /></label>
        </div>

        <label className="flex items-start gap-3 text-sm sm:col-span-2">
          <input type="checkbox" className="mt-0.5 h-4 w-4" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span className="text-ink-soft">I agree that Somosure may contact me about this application using the details above.</span>
        </label>

        {error && <p className="text-sm text-status-error sm:col-span-2">{error}</p>}
        <div className="sm:col-span-2">
          <Button type="submit" size="lg" disabled={busy}>{busy ? "Sending…" : "Send application"}</Button>
        </div>
      </form>
    </Card>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

interface Contact {
  id: string;
  label: string;
  full_name: string;
  phone: string | null;
  email: string | null;
}

interface Communication {
  id: string;
  channel: string;
  direction: string;
  subject: string | null;
  body: string | null;
  created_at: string;
}

interface CustomerDetail {
  id: string;
  full_name: string;
  email: string | null;
  phone: string;
  id_number: string | null;
  kra_pin: string | null;
  lead_source: string | null;
  consent_marketing: boolean;
  created_at: string;
  contacts: Contact[];
  communications: Communication[];
}

const emptyContact = { label: "", full_name: "", phone: "", email: "" };

export default function AdminCustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [contactForm, setContactForm] = useState(emptyContact);
  const [addingContact, setAddingContact] = useState(false);

  async function load() {
    try {
      setCustomer(await api.get<CustomerDetail>(`/api/v1/admin/customers/${params.id}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load customer");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  async function addContact() {
    if (!contactForm.label.trim() || !contactForm.full_name.trim()) return;
    setAddingContact(true);
    try {
      await api.post(`/api/v1/admin/customers/${params.id}/contacts`, {
        label: contactForm.label,
        full_name: contactForm.full_name,
        phone: contactForm.phone || null,
        email: contactForm.email || null,
      });
      setContactForm(emptyContact);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add contact");
    } finally {
      setAddingContact(false);
    }
  }

  async function removeContact(contactId: string) {
    await api.del(`/api/v1/admin/customers/${params.id}/contacts/${contactId}`);
    load();
  }

  if (error) return <main className="mx-auto max-w-3xl px-6 py-12 text-status-error">{error}</main>;
  if (!customer) return <main className="mx-auto max-w-3xl px-6 py-12 text-ink-soft">Loading…</main>;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-bold">{customer.full_name}</h1>
      <p className="mt-1 text-ink-soft">
        {customer.phone}
        {customer.email ? ` · ${customer.email}` : ""}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {customer.lead_source && <Badge tone="brand">{customer.lead_source.replace(/_/g, " ")}</Badge>}
        {customer.consent_marketing && <Badge tone="success">Marketing consent</Badge>}
        {customer.id_number && <Badge tone="neutral">ID {customer.id_number}</Badge>}
        {customer.kra_pin && <Badge tone="neutral">KRA {customer.kra_pin}</Badge>}
      </div>

      <div className="mt-4 flex gap-3 text-sm">
        <a href={`/admin/policies?search=${encodeURIComponent(customer.full_name)}`} className="text-brand-deep underline">
          View policies
        </a>
        <a href={`/admin/payments?search=${encodeURIComponent(customer.full_name)}`} className="text-brand-deep underline">
          View payments
        </a>
      </div>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Other contacts</h2>
        <p className="text-sm text-ink-soft">Next of kin, spouse, or anyone else on file for this customer.</p>

        <div className="mt-3 flex flex-col gap-2">
          {customer.contacts.map((c) => (
            <Card key={c.id} className="flex items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{c.full_name}</h3>
                  <Badge tone="neutral">{c.label}</Badge>
                </div>
                <p className="mt-1 text-xs text-ink-soft">{[c.phone, c.email].filter(Boolean).join(" · ") || "No contact details"}</p>
              </div>
              <Button variant="ghost" onClick={() => removeContact(c.id)}>
                Remove
              </Button>
            </Card>
          ))}
          {customer.contacts.length === 0 && <p className="text-sm text-ink-soft">None added yet.</p>}
        </div>

        <Card className="mt-3 flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-4">
            <Input label="Label" placeholder="Next of kin" value={contactForm.label} onChange={(e) => setContactForm({ ...contactForm, label: e.target.value })} />
            <Input label="Name" value={contactForm.full_name} onChange={(e) => setContactForm({ ...contactForm, full_name: e.target.value })} />
            <Input label="Phone" value={contactForm.phone} onChange={(e) => setContactForm({ ...contactForm, phone: e.target.value })} />
            <Input label="Email" value={contactForm.email} onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })} />
          </div>
          <div>
            <Button onClick={addContact} disabled={addingContact}>
              {addingContact ? "Adding…" : "Add contact"}
            </Button>
          </div>
        </Card>
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold">Communications</h2>
        <p className="text-sm text-ink-soft">Every contact-form message and WhatsApp exchange logged for this customer.</p>

        <div className="mt-3 flex flex-col gap-2">
          {customer.communications.map((c) => (
            <Card key={c.id} className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <Badge tone={c.direction === "inbound" ? "brand" : "neutral"}>{c.direction}</Badge>
                <Badge tone="neutral">{c.channel}</Badge>
                <span className="text-xs text-ink-soft">{new Date(c.created_at).toLocaleString("en-KE")}</span>
              </div>
              {c.subject && <p className="text-sm font-medium">{c.subject}</p>}
              {c.body && <p className="text-sm text-ink-soft">{c.body}</p>}
            </Card>
          ))}
          {customer.communications.length === 0 && <p className="text-sm text-ink-soft">No communications logged yet.</p>}
        </div>
      </section>
    </main>
  );
}

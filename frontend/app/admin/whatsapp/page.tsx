"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

interface Conversation {
  id: string;
  phone_number: string;
  customer_id: string | null;
  state: string;
  last_message_at: string;
}

interface Message {
  id: string;
  direction: string;
  body: string;
  created_at: string;
}

export default function WhatsAppInboxPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Conversation[]>("/api/v1/admin/whatsapp/conversations").then(setConversations).catch((e) => setError(e.message));
  }, []);

  async function openConversation(c: Conversation) {
    setSelected(c);
    const msgs = await api.get<Message[]>(`/api/v1/admin/whatsapp/conversations/${c.id}/messages`);
    setMessages(msgs);
  }

  if (error) return <main className="mx-auto max-w-4xl px-6 py-12 text-status-error">{error}</main>;

  return (
    <main className="mx-auto max-w-8xl px-6 py-12">
      <h1 className="text-2xl font-bold">WhatsApp</h1>
      <p className="mt-1 text-ink-soft">Conversations logged from the WhatsApp webhook, linked to CRM.</p>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <div className="flex flex-col gap-2 md:col-span-1">
          {conversations.map((c) => (
            <button key={c.id} onClick={() => openConversation(c)} className="text-left">
              <Card className={`text-sm ${selected?.id === c.id ? "border-brand-deep" : ""}`}>
                <p className="font-mono">{c.phone_number}</p>
                <Badge tone="neutral">{c.state}</Badge>
              </Card>
            </button>
          ))}
          {conversations.length === 0 && <p className="text-ink-soft">No conversations yet.</p>}
        </div>

        <div className="md:col-span-2">
          {selected ? (
            <div className="flex flex-col gap-2">
              {messages.map((m) => (
                <div key={m.id} className={`max-w-[80%] rounded-control px-4 py-2 text-sm ${m.direction === "inbound" ? "bg-neutral" : "ml-auto bg-brand-tint"}`}>
                  {m.body}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-ink-soft">Select a conversation to view messages.</p>
          )}
        </div>
      </div>
    </main>
  );
}

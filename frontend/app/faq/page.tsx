"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";

interface Faq {
  id: string;
  question: string;
  answer: string;
  display_order: number;
}

export default function FaqPage() {
  const [faqs, setFaqs] = useState<Faq[]>([]);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/v1/faqs`)
      .then((r) => r.json())
      .then(setFaqs)
      .catch(() => {});
  }, []);

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-bold">Frequently asked questions</h1>
      <div className="mt-6 flex flex-col gap-4">
        {faqs.map((f) => (
          <Card key={f.id}>
            <h2 className="font-semibold">{f.question}</h2>
            <p className="mt-2 text-sm text-ink-soft">{f.answer}</p>
          </Card>
        ))}
        {faqs.length === 0 && <p className="text-ink-soft">No questions published yet.</p>}
      </div>
    </main>
  );
}

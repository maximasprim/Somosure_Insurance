"use client";

import { useEffect, useState } from "react";
import { BookOpen } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { WhatsAppButton } from "@/components/WhatsAppButton";
import { Reveal } from "@/components/Reveal";
import { Card } from "@/components/ui/Card";

interface ContentItem {
  id: string;
  slug: string;
  title: string;
  body: string;
}

export default function ResourcesPage() {
  const [articles, setArticles] = useState<ContentItem[]>([]);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/v1/content`)
      .then((r) => r.json())
      .then(setArticles)
      .catch(() => {});
  }, []);

  return (
    <main>
      <Navbar />
      <section className="mx-auto max-w-4xl px-6 py-16 md:px-12">
        <Reveal>
          <h1 className="text-3xl font-extrabold md:text-4xl">Insurance, explained plainly</h1>
          <p className="mt-3 max-w-prose text-ink-soft">
            Guides on how cover actually works, written without jargon - so you know what you're buying before you buy it.
          </p>
        </Reveal>

        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {articles.map((a, i) => (
            <Reveal key={a.id} delay={i * 0.05}>
              <Card className="flex h-full flex-col gap-3">
                <BookOpen className="h-5 w-5 text-brand-deep" />
                <h2 className="font-display text-lg font-bold">{a.title}</h2>
                <p className="line-clamp-3 text-sm text-ink-soft">{a.body}</p>
              </Card>
            </Reveal>
          ))}
          {articles.length === 0 && (
            <p className="text-ink-soft sm:col-span-2">
              No guides published yet - check back soon, or see our <a href="/faq" className="text-brand-deep hover:underline">FAQ</a> in the meantime.
            </p>
          )}
        </div>
      </section>
      <Footer />
      <WhatsAppButton />
    </main>
  );
}

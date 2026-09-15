import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { WhatsAppButton } from "@/components/WhatsAppButton";
import { Reveal } from "@/components/Reveal";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

const PRODUCTS = [
  { name: "Motor insurance", href: "/quote/motor", desc: "Comprehensive or third-party cover for your car, from insurers who compete for your business." },
  { name: "Medical insurance", href: "/quote/medical", desc: "Individual or family health cover, matched to the hospital tier you actually want." },
  { name: "Life insurance", href: "/quote/life", desc: "Term cover that protects the people who depend on your income." },
  { name: "Home insurance", href: "/quote/home", desc: "Cover for your house or apartment against fire, theft, and damage." },
  { name: "Travel insurance", href: "/quote/travel", desc: "Medical emergencies, lost luggage, and trip cancellation - sorted before you fly." },
  { name: "Business insurance", href: "/quote/business", desc: "Property, liability, or combined cover sized to your business." },
  { name: "Personal accident", href: "/quote/personal_accident", desc: "A lump-sum payout if an accident affects your ability to work." },
];

export default function InsurancePage() {
  return (
    <main>
      <Navbar />
      <section className="mx-auto max-w-4xl px-6 py-16 md:px-12">
        <Reveal>
          <h1 className="text-3xl font-extrabold md:text-4xl">Insurance, by what you're protecting</h1>
          <p className="mt-3 max-w-prose text-ink-soft">
            Every product below compares quotes from multiple insurers, so you're not stuck taking whatever one company offers.
          </p>
        </Reveal>

        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {PRODUCTS.map((p, i) => (
            <Reveal key={p.href} delay={i * 0.05}>
              <Card className="flex h-full flex-col gap-3">
                <h2 className="font-display text-lg font-bold">{p.name}</h2>
                <p className="text-sm text-ink-soft">{p.desc}</p>
                <Link href={p.href} className="mt-auto">
                  <Button size="md">Get a quote</Button>
                </Link>
              </Card>
            </Reveal>
          ))}
        </div>
      </section>
      <Footer />
      <WhatsAppButton />
    </main>
  );
}

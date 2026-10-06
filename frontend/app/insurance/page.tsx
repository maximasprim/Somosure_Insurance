import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { WhatsAppButton } from "@/components/WhatsAppButton";
import { Reveal } from "@/components/Reveal";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ProductWheel } from "@/components/ProductWheel";

const PRODUCTS = [
  { category: "motor", name: "Motor insurance", href: "/quote/motor", desc: "Comprehensive or third-party cover for your car, from insurers who compete for your business." },
  { category: "medical", name: "Medical insurance", href: "/quote/medical", desc: "Individual or family health cover, matched to the hospital tier you actually want." },
  { category: "life", name: "Life insurance", href: "/quote/life", desc: "Term cover that protects the people who depend on your income." },
  { category: "property", name: "Property insurance", href: "/quote/property", desc: "Cover your home, rental property or business premises against fire, theft and burglary, and more - pick only what you need." },
  { category: "travel", name: "Travel insurance", href: "/quote/travel", desc: "Medical emergencies, lost luggage, and trip cancellation - sorted before you fly." },
  { category: "personal_accident", name: "Personal accident", href: "/quote/personal_accident", desc: "A lump-sum payout if an accident affects your ability to work." },
  { category: "professional_indemnity", name: "Professional indemnity", href: "/quote/professional_indemnity", desc: "Cover against claims of negligence or error in the professional advice or service you provide." },
  { category: "wiba", name: "WIBA (Work Injury Benefits)", href: "/quote/wiba", desc: "Statutory cover for your employees against workplace injury, disability, or death - as required by the Work Injury Benefits Act." },
  { category: "cargo", name: "Cargo insurance", href: "/quote/cargo", desc: "Local and marine cover for goods in transit - by road, rail, sea or air.", comingSoon: true },
  { category: "hull", name: "Hull insurance", href: "/quote/hull", desc: "Cover for boats, vessels and their machinery.", comingSoon: true },
  { category: "cybersecurity", name: "Cybersecurity insurance", href: "/quote/cybersecurity", desc: "Protection against data breaches, ransomware and the downtime they cause.", comingSoon: true },
];

export default function InsurancePage() {
  return (
    <main>
      <Navbar />
      <section className="mx-auto max-w-7xl px-6 py-16 md:px-12">
        <Reveal className="flex flex-col items-center">
          <h1 className="text-3xl font-extrabold md:text-4xl">Insurance, by what you're protecting</h1>
          <p className="mt-3 max-w-prose text-ink-soft tight tracking-wide text-center text-xs md:text-sm">
            Every product below compares quotes from multiple insurers, so you're <br></br> not stuck taking whatever one company offers.
          </p>
        </Reveal>

        <Reveal delay={0.1}>
          <div className="mt-10">
            <ProductWheel items={PRODUCTS} />
          </div>
        </Reveal>

        <div className="mt-16 grid gap-4 sm:grid-cols-1 md:grid-cols-3 lg:grid-cols-4">
          {PRODUCTS.map((p, i) => (
            <Reveal key={p.href} delay={i * 0.05}>
              <Card className="flex h-full flex-col gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-display text-lg font-bold">{p.name}</h2>
                  {"comingSoon" in p && p.comingSoon && <Badge tone="brand">Coming soon</Badge>}
                </div>
                <p className="text-sm text-ink-soft">{p.desc}</p>
                <Link href={p.href} className="mt-auto">
                  {"comingSoon" in p && p.comingSoon ? (
                    <Button size="md" variant="ghost">Talk to an agent</Button>
                  ) : (
                    <Button size="md">Get a quote</Button>
                  )}
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

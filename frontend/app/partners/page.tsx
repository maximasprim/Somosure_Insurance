import { Banknote, Briefcase, Building2, Car, Landmark, Ship, Store, Users } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { WhatsAppButton } from "@/components/WhatsAppButton";
import { Reveal } from "@/components/Reveal";
import { Card } from "@/components/ui/Card";
import { PartnerApplicationForm } from "@/components/partners/PartnerApplicationForm";

export const metadata = {
  title: "Become a partner | Somosure",
  description: "Dealerships, importers, employers, businesses, banks, SACCOs and agents: partner with Somosure and send your customers to quality insurance.",
};

const WHO = [
  { icon: Car, name: "Car dealers", text: "Every buyer drives away insured." },
  { icon: Ship, name: "Vehicle importers", text: "Cover ready for each vehicle you bring in." },
  { icon: Briefcase, name: "Employers", text: "Cover options for your staff." },
  { icon: Store, name: "Small businesses", text: "Offer insurance to your own customers." },
  { icon: Landmark, name: "Banks", text: "Insurance alongside your products." },
  { icon: Users, name: "SACCOs", text: "Cover for your members." },
  { icon: Banknote, name: "Agents", text: "A wider range to offer your clients." },
  { icon: Building2, name: "Corporates", text: "Group and company cover." },
];

const STEPS = [
  { n: "1", title: "Tell us about your business", text: "Fill in the short form below - it takes a couple of minutes." },
  { n: "2", title: "We review and get in touch", text: "Our team looks at every application and contacts you to talk it through." },
  { n: "3", title: "Start working together", text: "Once approved, we agree how you'll refer or submit customers and how you'll be rewarded." },
];

export default function BecomeAPartnerPage() {
  return (
    <main>
      <Navbar />

      <section className="mx-auto max-w-5xl px-6 pb-6 pt-14 md:px-12 md:pt-20">
        <Reveal>
          <h1 className="text-3xl font-extrabold md:text-5xl">Partner with Somosure</h1>
          <p className="mt-4 max-w-2xl text-lg text-ink-soft">
            Your customers need insurance. We make it simple to compare and buy, and we reward the businesses that send people our way.
          </p>
        </Reveal>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-8 md:px-12">
        <Reveal><h2 className="text-xl font-bold md:text-2xl">Who it&apos;s for</h2></Reveal>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 md:grid-cols-4">
          {WHO.map((w, i) => (
            <Reveal key={w.name} delay={i * 0.04}>
              <Card className="flex h-full flex-col gap-2 p-5">
                <w.icon className="h-6 w-6 text-brand-deep" aria-hidden />
                <p className="font-semibold">{w.name}</p>
                <p className="text-sm text-ink-soft">{w.text}</p>
              </Card>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-8 md:px-12">
        <Reveal><h2 className="text-xl font-bold md:text-2xl">How it works</h2></Reveal>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 0.08}>
              <Card className="flex h-full flex-col gap-2 p-5">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-tint font-bold">{s.n}</span>
                <p className="font-semibold">{s.title}</p>
                <p className="text-sm text-ink-soft">{s.text}</p>
              </Card>
            </Reveal>
          ))}
        </div>
      </section>

      <section id="apply" className="mx-auto max-w-3xl px-6 py-10 md:px-12">
        <Reveal>
          <h2 className="text-xl font-bold md:text-2xl">Apply to become a partner</h2>
          <p className="mb-6 mt-2 text-ink-soft">No obligation - we&apos;ll talk it through with you first.</p>
        </Reveal>
        <PartnerApplicationForm />
      </section>

      <Footer />
      <WhatsAppButton />
    </main>
  );
}

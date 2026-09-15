import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { WhatsAppButton } from "@/components/WhatsAppButton";
import { Reveal } from "@/components/Reveal";
import { Card } from "@/components/ui/Card";

export default function AboutPage() {
  return (
    <main>
      <Navbar />
      <section className="mx-auto max-w-3xl px-6 py-16 md:px-12">
        <Reveal>
          <h1 className="text-3xl font-extrabold md:text-4xl">About Somosure</h1>
          <p className="mt-4 max-w-prose text-ink-soft">
            Somosure is a digital insurance platform built for the Kenyan market. Instead of visiting one insurer at a
            time or working through a single agent's limited options, you compare real quotes from multiple providers,
            apply, pay, and manage your policy - all from one account.
          </p>
          <p className="mt-4 max-w-prose text-ink-soft">
            We handle the paperwork, the follow-ups, and the renewal reminders, so getting covered feels like an
            ordinary online purchase rather than a trip to a government office.
          </p>
        </Reveal>

        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          {[
            { title: "Multiple insurers", body: "Compare real quotes side by side instead of guessing which insurer is fair." },
            { title: "Digital-first", body: "Apply, pay, and receive your policy documents without visiting a branch." },
            { title: "Real support", body: "Talk to a person on WhatsApp or by phone whenever the process gets confusing." },
          ].map((item, i) => (
            <Reveal key={item.title} delay={i * 0.08}>
              <Card>
                <h2 className="font-semibold">{item.title}</h2>
                <p className="mt-2 text-sm text-ink-soft">{item.body}</p>
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

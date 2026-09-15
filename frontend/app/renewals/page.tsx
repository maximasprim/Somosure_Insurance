import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { WhatsAppButton } from "@/components/WhatsAppButton";
import { Reveal } from "@/components/Reveal";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export default function RenewalsPage() {
  return (
    <main>
      <Navbar />
      <section className="mx-auto max-w-2xl px-6 py-16 md:px-12">
        <h1 className="text-3xl font-extrabold md:text-4xl">Renewing your policy</h1>
        <p className="mt-4 text-ink-soft">
          We'll remind you well before your policy expires - starting 60 days out, then again as the date gets
          closer. You don't have to track the date yourself.
        </p>

        <div className="mt-8 flex flex-col gap-4">
          <Card>
            <h2 className="font-semibold">Already have a policy with us?</h2>
            <p className="mt-2 text-sm text-ink-soft">
              Log in to see your renewal date and renew directly from your account.
            </p>
            <Link href="/dashboard" className="mt-4 inline-block">
              <Button size="md">Go to my dashboard</Button>
            </Link>
          </Card>
          <Card>
            <h2 className="font-semibold">Renewing from another insurer?</h2>
            <p className="mt-2 text-sm text-ink-soft">
              You can still get a fresh comparison of quotes before your current policy lapses.
            </p>
            <Link href="/quote/motor" className="mt-4 inline-block">
              <Button size="md" variant="ghost">Compare quotes</Button>
            </Link>
          </Card>
        </div>
      </section>
      <Footer />
      <WhatsAppButton />
    </main>
  );
}

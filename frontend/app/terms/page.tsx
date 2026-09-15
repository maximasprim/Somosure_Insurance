import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";

export default function TermsPage() {
  return (
    <main>
      <Navbar />
      <section className="mx-auto max-w-2xl px-6 py-16 md:px-12">
        <h1 className="text-3xl font-extrabold">Terms of service</h1>
        <p className="mt-4 text-ink-soft">
          This page is a placeholder. Somosure's actual terms of service - covering the platform's role as broker or
          agent, payment terms, cancellation rights, and dispute resolution - need to be drafted and reviewed by
          legal counsel before this platform handles real transactions.
        </p>
      </section>
      <Footer />
    </main>
  );
}

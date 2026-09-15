import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";

export default function PrivacyPage() {
  return (
    <main>
      <Navbar />
      <section className="mx-auto max-w-2xl px-6 py-16 md:px-12">
        <h1 className="text-3xl font-extrabold">Privacy policy</h1>
        <p className="mt-4 text-ink-soft">
          This page is a placeholder. Somosure's actual privacy policy - covering what customer data is collected,
          how it's used, retention periods, and data protection rights under Kenya's Data Protection Act - needs to
          be drafted and reviewed by legal counsel before this platform handles real customer data.
        </p>
      </section>
      <Footer />
    </main>
  );
}

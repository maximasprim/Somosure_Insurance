import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { WhatsAppButton } from "@/components/WhatsAppButton";

/**
 * Shared shell for every /quote/* flow (motor, medical, life, home,
 * travel, business, personal_accident). Before this, each quote page was
 * a bare <main> with no nav at all - once someone started a quote they
 * had no way back to Claims/FAQ/home except the browser back button.
 * Matches the same Navbar/Footer pattern already used by the marketing
 * pages (see app/renewals/page.tsx) rather than introducing a new one.
 */
export default function QuoteLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      {children}
      <Footer />
      <WhatsAppButton />
    </div>
  );
}

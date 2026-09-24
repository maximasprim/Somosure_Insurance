import { GenericQuoteFlow } from "@/components/quote/GenericQuoteFlow";
import { CATEGORY_CONFIGS } from "@/lib/quoteFields";

export default function ProfessionalIndemnityQuotePage() {
  return <GenericQuoteFlow config={CATEGORY_CONFIGS["professional_indemnity"]} />;
}

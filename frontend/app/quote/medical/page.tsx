import { GenericQuoteFlow } from "@/components/quote/GenericQuoteFlow";
import { CATEGORY_CONFIGS } from "@/lib/quoteFields";

export default function MedicalQuotePage() {
  return <GenericQuoteFlow config={CATEGORY_CONFIGS["medical"]} />;
}

import { GenericQuoteFlow } from "@/components/quote/GenericQuoteFlow";
import { CATEGORY_CONFIGS } from "@/lib/quoteFields";

export default function PersonalAccidentQuotePage() {
  return <GenericQuoteFlow config={CATEGORY_CONFIGS["personal_accident"]} />;
}

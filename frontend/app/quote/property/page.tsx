import { GenericQuoteFlow } from "@/components/quote/GenericQuoteFlow";
import { CATEGORY_CONFIGS } from "@/lib/quoteFields";

export default function PropertyQuotePage() {
  return <GenericQuoteFlow config={CATEGORY_CONFIGS["property"]} />;
}

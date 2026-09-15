import { GenericQuoteFlow } from "@/components/quote/GenericQuoteFlow";
import { CATEGORY_CONFIGS } from "@/lib/quoteFields";

export default function LifeQuotePage() {
  return <GenericQuoteFlow config={CATEGORY_CONFIGS["life"]} />;
}

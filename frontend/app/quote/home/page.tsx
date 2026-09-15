import { GenericQuoteFlow } from "@/components/quote/GenericQuoteFlow";
import { CATEGORY_CONFIGS } from "@/lib/quoteFields";

export default function HomeQuotePage() {
  return <GenericQuoteFlow config={CATEGORY_CONFIGS["home"]} />;
}

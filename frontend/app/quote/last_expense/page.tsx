import { GenericQuoteFlow } from "@/components/quote/GenericQuoteFlow";
import { CATEGORY_CONFIGS } from "@/lib/quoteFields";

export default function LastExpenseQuotePage() {
  return <GenericQuoteFlow config={CATEGORY_CONFIGS["last_expense"]} />;
}

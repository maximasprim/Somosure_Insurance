import { redirect } from "next/navigation";

// Home and business insurance are now one product: property insurance.
// This keeps old links, bookmarks and shared URLs working.
export default function LegacyQuotePage() {
  redirect("/quote/property");
}

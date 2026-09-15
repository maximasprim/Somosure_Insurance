import type { Metadata } from "next";
import { Manrope, Public_Sans } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  weight: ["500", "700", "800"],
  variable: "--font-manrope",
});

const publicSans = Public_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-public-sans",
});

export const metadata: Metadata = {
  title: "Somosure Insurance - Insurance made simpler",
  description:
    "Compare, understand, buy and manage your insurance from one trusted platform.",
  metadataBase: new URL("https://somosure.co.ke"),
  openGraph: {
    title: "Somosure Insurance - Insurance made simpler",
    description: "Compare, understand, buy and manage your insurance from one trusted platform.",
    url: "https://somosure.co.ke",
    siteName: "Somosure Insurance",
    locale: "en_KE",
    type: "website",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${manrope.variable} ${publicSans.variable}`}>
      <body>{children}</body>
    </html>
  );
}

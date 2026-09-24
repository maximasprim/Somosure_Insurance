"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ShieldCheck, Zap, Users, BellRing, Quote } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { WhatsAppButton } from "@/components/WhatsAppButton";
import { Reveal } from "@/components/Reveal";
import { AnimatedCounter } from "@/components/AnimatedCounter";
import Image from "next/image";
import HeroBackground from "@/assets/Hero_bg.jpg";
import BritamLogo from "@/assets/Britam logo.png";
import MonarchLogo from "@/assets/Monarch-Logo.png";
import CicLogo from "@/assets/CIC_Group_Logo.webp";
import PioneerLogo from "@/assets/pioneerlogo1.png";
import JubileeLogo from "@/assets/jubilee-group-logo.png";
import ApaLogo from "@/assets/Apa_logo.png";
import AmarcoLogo from "@/assets/Amarco_logo.png";

import { ProductWheel } from "@/components/ProductWheel";

const INSURE_OPTIONS = [
  { category: "motor", name: "Car", href: "/quote/motor", desc: "Comprehensive or third-party cover for your car." },
  { category: "medical", name: "Health", href: "/quote/medical", desc: "Individual or family medical cover." },
  { category: "home", name: "Home", href: "/quote/home", desc: "Cover for your house or apartment." },
  { category: "business", name: "Business", href: "/quote/business", desc: "Property, liability, or combined business cover." },
  { category: "travel", name: "Travel", href: "/quote/travel", desc: "Cover for medical emergencies, luggage, and cancellations." },
  { category: "life", name: "Life", href: "/quote/life", desc: "Term cover that protects your dependents." },
  { category: "personal_accident", name: "Personal accident", href: "/quote/personal_accident", desc: "A lump-sum payout if an accident affects your ability to work." },
  { category: "professional_indemnity", name: "Professional indemnity", href: "/quote/professional_indemnity", desc: "Cover against claims of negligence or error in your professional service." },
  { category: "wiba", name: "WIBA", href: "/quote/wiba", desc: "Statutory cover for your employees against workplace injury." },
];

const TRUST_ROW = [
  "Quotes from multiple insurers",
  "Secure M-Pesa and card payments",
  "Policy documents in your account",
  "Real people on WhatsApp",
];

const STEPS = [
  { step: "Tell us what you're insuring", detail: "A few plain questions, not a form." },
  { step: "Compare real quotes", detail: "Side by side, from every insurer we work with." },
  { step: "Pay and get covered", detail: "M-Pesa, card, or bank transfer - documents land in your account." },
];

// Illustrative figures - replace with real numbers before this platform
// launches. Shown here to demonstrate the section, not as a claim about
// current usage.
const STATS = [
  { value: 7, suffix: "", label: "insurance products" },
  { value: 6, suffix: "+", label: "insurers compared per quote" },
  { value: 2, suffix: " min", label: "average time to a quote", prefix: "< " },
  { value: 60, suffix: "-day", label: "advance renewal reminders" },
];

const WHY_SOMOSURE = [
  {
    icon: ShieldCheck,
    title: "Compare before you commit",
    detail: "See what different insurers actually charge for the same cover, instead of taking one company's word for it.",
  },
  {
    icon: Zap,
    title: "Nothing gets lost in paperwork",
    detail: "Applications, documents, and payments live in your account - not a folder of texts and forwarded emails.",
  },
  {
    icon: BellRing,
    title: "Renewals that don't sneak up on you",
    detail: "We track your expiry dates and remind you with enough time to actually act, not the day before.",
  },
  {
    icon: Users,
    title: "A person, not just a portal",
    detail: "When something's unclear, reach a real person on WhatsApp instead of waiting on hold.",
  },
];

const TESTIMONIALS = [
  { quote: "I compared three insurers for my car in under five minutes and paid straight from my phone.", role: "Motor insurance customer, Nairobi" },
  { quote: "The renewal reminder actually gave me time to shop around instead of auto-renewing out of panic.", role: "Medical insurance customer, Mombasa" },
  { quote: "I could see exactly what my excess and exclusions were before I paid - no surprises later.", role: "Home insurance customer, Kisumu" },
];

// Labeled honestly to match what's actually integrated today - see
// docs/PROVIDER_LANDSCAPE.md. Real insurer names/logos are never shown
// without an actual signed partnership.
const MARKETPLACE_PARTNERS = [
  { name: "Britam Insurance", logo: BritamLogo },
  { name: "Monarch Insurance", logo: MonarchLogo },
  { name: "CIC Insurance", logo: CicLogo },
  { name: "Pioneer Insurance", logo: PioneerLogo },
  { name: "Jubilee Insurance", logo: JubileeLogo },
  { name: "APA Insurance", logo: ApaLogo },
  { name: "Amarco Insurance", logo: AmarcoLogo },
];

export default function HomePage() {
  return (
    <main className="overflow-x-hidden">
      <Navbar />

      {/* Hero */}
      <section className="relative overflow-hidden">
        {/* Soft decorative blobs - pure CSS, no imagery dependency */}
        <Image
          src={HeroBackground}
          alt="Salvage car"
          fill
          priority
          className="-z-10 object-cover"
        />
        <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 bg-brand/30" />

        <div className="mx-auto grid max-w-7xl gap-10 px-6 pb-16 pt-14 md:grid-cols-2 md:gap-16 md:px-12 md:pt-24">
          <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-brand/20 blur-3xl" />
          <div aria-hidden className="pointer-events-none absolute -left-32 top-40 h-72 w-72 rounded-full bg-brand/10 blur-3xl" />

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.21, 0.47, 0.32, 0.98] }}
            className="relative flex flex-col justify-center gap-6"
          >
            <span className="inline-flex w-fit items-center gap-2 rounded-full bg-brand-tint px-3 py-1 text-xs font-semibold text-ink">
              <ShieldCheck className="h-3.5 w-3.5" /> Licensed Insurance Agency
            </span>
            <h1 className="max-w-[14ch] text-4xl font-extrabold leading-[1.05] text-white md:text-6xl">
              Insurance Made Simpler
            </h1>
            <p className="max-w-prose text-lg text-white/90">
              Compare, understand, buy and manage your insurance from one trusted platform.
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <Link href="/quote/motor"><Button className="px-6 py-2 rounded-full">Get a quote</Button></Link>
              <Link href="/contact"><Button className="px-6 py-2 rounded-full" variant="ghost">Talk to an advisor</Button></Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.15, ease: [0.21, 0.47, 0.32, 0.98] }}
          >
            <Card className="relative flex flex-col gap-8 overflow-hidden shadow-[0_20px_60px_-15px_rgba(232,161,0,0.35)] bg-[radial-gradient(ellipse_at_center,transparent_45%,#FFF3D6_90%,rgba(255,197,61,0.45)_100%)]">
              <div>
                <h2 className="text-xl font-bold">What do you want to insure?</h2>
                <p className="mt-1 text-sm text-ink-soft">Pick one to start a quote - takes about two minutes.</p>
              </div>
              <ProductWheel items={INSURE_OPTIONS} compact />
            </Card>
          </motion.div>
        </div>
      </section>

      {/* Trust row */}
      <section className="border-y border-neutral-border bg-neutral px-6 py-8 md:px-12">
        <ul className="mx-auto flex max-w-7xl flex-wrap justify-center gap-x-10 gap-y-3 text-sm font-medium text-ink-soft">
          {TRUST_ROW.map((item) => (
            <li key={item} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-deep" />
              {item}
            </li>
          ))}
        </ul>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-7xl px-6 py-20 md:px-12">
        <Reveal><h2 className="text-2xl font-bold md:text-3xl">How Somosure works</h2></Reveal>
        <div className="mt-10 grid gap-8 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <Reveal key={s.step} delay={i * 0.1}>
              <div className="flex flex-col gap-2">
                <span className="font-display text-3xl font-extrabold text-brand-deep">{i + 1}</span>
                <h3 className="text-lg font-semibold">{s.step}</h3>
                <p className="text-sm text-ink-soft">{s.detail}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Stats */}
      <section className="bg-ink px-6 py-16 md:px-12">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-8 md:grid-cols-4">
          {STATS.map((s, i) => (
            <Reveal key={s.label} delay={i * 0.08}>
              <p className="font-display text-3xl font-extrabold text-brand md:text-4xl">
                <AnimatedCounter value={s.value} suffix={s.suffix} prefix={s.prefix} />
              </p>
              <p className="mt-1 text-sm text-white/70">{s.label}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Why Somosure */}
      <section className="mx-auto max-w-7xl px-6 py-20 md:px-12">
        <Reveal><h2 className="text-2xl font-bold md:text-3xl">Why Somosure</h2></Reveal>
        <div className="mt-10 grid gap-8 sm:grid-cols-2">
          {WHY_SOMOSURE.map((item, i) => (
            <Reveal key={item.title} delay={i * 0.08}>
              <div className="flex gap-4">
                <div className="flex h-11 w-11 flex-none items-center justify-center rounded-control bg-brand-tint text-ink">
                  <item.icon className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold">{item.title}</h3>
                  <p className="mt-1 text-sm text-ink-soft">{item.detail}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Marketplace partners strip */}
      <section className="border-y border-neutral-border bg-neutral py-8">
        <Reveal>
          <p className="mb-6 text-center text-xs font-semibold uppercase tracking-wide text-ink-soft">
            Comparing quotes from
          </p>
        </Reveal>
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-center gap-x-10 gap-y-6 px-6">
          {MARKETPLACE_PARTNERS.map((partner) => (
            <Image
              key={partner.name}
              src={partner.logo}
              alt={partner.name}
              className="h-12 w-auto object-contain opacity-60 grayscale transition hover:opacity-100 hover:grayscale-0"
            />
          ))}
        </div>
      </section>

      {/* Testimonials */}
      <section className="px-6 py-16 md:px-12">
        <div className="mx-auto max-w-7xl">
          <Reveal><h2 className="text-2xl font-bold md:text-3xl">What customers say</h2></Reveal>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {TESTIMONIALS.map((t, i) => (
              <Reveal key={t.role} delay={i * 0.1}>
                <Card className="flex h-full flex-col gap-4">
                  <Quote className="h-6 w-6 text-brand-deep" />
                  <p className="text-ink">"{t.quote}"</p>
                  <p className="mt-auto text-sm text-ink-soft">{t.role}</p>
                </Card>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-6 pb-16 md:px-12">
        <Reveal>
          <Card className="flex flex-col items-start gap-4 bg-ink text-ink-soft md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-xl font-bold">Renewal Coming Up?</h2>
              <p className="mt-1 text-sm text-brand-deep/80">
                We'll pull your policy details and get you fresh quotes before it lapses.
              </p>
            </div>
            <Link href="/renewals"><Button variant="primary">Check my renewal</Button></Link>
          </Card>
        </Reveal>
      </section>

      <Footer />
      <WhatsAppButton />
    </main>
  );
}

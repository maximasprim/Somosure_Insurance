import Link from "next/link";
import { Card } from "@/components/ui/Card";
import {
  Users,
  FileText,
  ShieldAlert,
  Banknote,
  UserCheck,
  CalendarClock,
  Building2,
  Percent,
  Zap,
  Tag,
  MessageCircle,
  BarChart3,
  Search,
} from "lucide-react";

// The shortcut grid that used to be the whole admin overview page. It now sits
// at the bottom of the analytics dashboard, so nothing that was reachable from
// the overview has been lost - and it is the only thing a staff role without
// access to the analytics sees.
const SECTIONS = [
  {
    title: "Sales & CRM",
    items: [
      { label: "Leads", href: "/admin/leads", icon: Users, blurb: "Kanban pipeline and lead activity." },
      { label: "Applications", href: "/admin/applications", icon: FileText, blurb: "Underwriting queue for submitted applications." },
    ],
  },
  {
    title: "Underwriting",
    items: [
      { label: "Claims", href: "/admin/claims", icon: ShieldAlert, blurb: "Track and progress customer claims." },
      { label: "Financing", href: "/admin/financing", icon: Banknote, blurb: "Bidii Credit premium financing requests." },
      { label: "Loan officers", href: "/admin/loan-officers", icon: UserCheck, blurb: "IPF loan officers, their targets and commission." },
      { label: "Providers", href: "/admin/providers", icon: Building2, blurb: "Insurer/broker integrations and status." },
      { label: "Rate cards", href: "/admin/rate-cards", icon: Percent, blurb: "Configure AMACO, Pioneer, and future brokers' rates." },
    ],
  },
  {
    title: "Operations",
    items: [
      { label: "Automation", href: "/admin/automation", icon: Zap, blurb: "Event-triggered rules (renewals, reminders, stickers)." },
      { label: "Stickers", href: "/admin/stickers", icon: Tag, blurb: "Motor policy sticker issuance workflow." },
      { label: "WhatsApp", href: "/admin/whatsapp", icon: MessageCircle, blurb: "Webhook status and message templates." },
      { label: "Anniversaries", href: "/admin/anniversaries", icon: CalendarClock, blurb: "Renew all of a customer's covers on one date." },
    ],
  },
  {
    title: "Insights",
    items: [
      { label: "Reports", href: "/admin/reports", icon: BarChart3, blurb: "Management overview and provider CSV export." },
      { label: "Search", href: "/admin/search", icon: Search, blurb: "Global search across customers, policies, claims." },
    ],
  },
];

export function AdminQuickLinks() {
  return (
    <div className="flex flex-col gap-8">
      {SECTIONS.map((section) => (
        <div key={section.title}>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-soft">{section.title}</h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {section.items.map((item) => {
              const Icon = item.icon;
              return (
                <Link key={item.href} href={item.href}>
                  <Card className="flex h-full flex-col gap-2 transition-shadow hover:shadow-card">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-9 w-9 items-center justify-center rounded-control bg-brand-tint text-ink">
                        <Icon className="h-4.5 w-4.5" />
                      </span>
                      <h4 className="font-semibold">{item.label}</h4>
                    </div>
                    <p className="text-sm text-ink-soft">{item.blurb}</p>
                  </Card>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { WHATSAPP_NUMBER } from "@/components/WhatsAppButton";
import { api } from "@/lib/api";

const POLL_MS = 8000;

/**
 * "Under review" screen that watches the application itself. Before this,
 * the customer had to click "I've been notified it's approved" and hope -
 * if they clicked early the payment would fail with a confusing error.
 * Now we check the real status every few seconds and move them on to
 * payment the moment underwriting approves (or tell them straight away if
 * it was declined). The manual button stays as a fallback.
 */
export function ApprovalWaitStep({
  applicationId,
  reference,
  onApproved,
}: {
  applicationId: string;
  reference?: string;
  onApproved: () => void;
}) {
  const [status, setStatus] = useState<string>("submitted");
  const [checking, setChecking] = useState(false);
  const advanced = useRef(false);

  async function check() {
    setChecking(true);
    try {
      const res = await api.get<{ status: string }>(`/api/v1/applications/${applicationId}/status`);
      setStatus(res.status);
      if (res.status === "approved" && !advanced.current) {
        advanced.current = true;
        onApproved();
      }
      return res.status;
    } catch {
      /* transient - the next poll will retry */
      return null;
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => {
    let stopped = false;
    const id = window.setInterval(async () => {
      if (stopped) return;
      const s = await check();
      if (s === "approved" || s === "rejected") window.clearInterval(id);
    }, POLL_MS);
    return () => {
      stopped = true;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applicationId]);

  if (status === "rejected") {
    const waText = encodeURIComponent(`Hello Somosure, my application ${reference ?? ""} was declined - can an agent help me?`);
    return (
      <Card className="flex flex-col items-start gap-3">
        <h2 className="text-xl font-bold">We couldn&apos;t approve this application</h2>
        <p className="text-ink-soft">
          Application <span className="font-semibold text-ink">{reference}</span> wasn&apos;t approved as submitted. That
          is often fixable - an agent can look at it with you and suggest the next step.
        </p>
        <a
          href={`https://wa.me/${WHATSAPP_NUMBER}?text=${waText}`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 text-sm font-semibold text-brand-deep hover:underline"
        >
          <MessageCircle className="h-4 w-4" aria-hidden /> Talk to an agent on WhatsApp
        </a>
      </Card>
    );
  }

  return (
    <Card className="flex flex-col items-start gap-3">
      <h2 className="text-xl font-bold">Under review</h2>
      <p className="text-ink-soft">
        Your application <span className="font-semibold text-ink">{reference}</span> is with our underwriting team -
        usually a few hours. You can keep this page open: we&apos;ll check for you and take you straight to payment the
        moment it&apos;s approved. You&apos;ll also be notified.
      </p>
      <Button variant="ghost" onClick={check} disabled={checking}>
        {checking ? "Checking…" : "Check status now"}
      </Button>
    </Card>
  );
}

"use client";

import { useEffect } from "react";
import { rememberReferral } from "@/lib/referral";

/** Invisible: notes a ?ref=CODE in the address on any page, so the referrer is
 *  credited later. Renders nothing and never touches the page. */
export function RefCapture() {
  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get("ref");
    if (code) rememberReferral(code);
  }, []);
  return null;
}

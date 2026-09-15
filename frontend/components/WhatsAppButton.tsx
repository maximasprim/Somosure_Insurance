"use client";

import { motion } from "framer-motion";
import { MessageCircle } from "lucide-react";

// Placeholder number - replace with Somosure's real WhatsApp Business
// number once the WhatsApp integration (docs/WHATSAPP.md) is live with a
// real WABA. wa.me links work regardless of the Cloud API integration
// status, so this is safe to ship even before real credentials exist.
const WHATSAPP_NUMBER = "254700000000";

export function WhatsAppButton() {
  return (
    <motion.a
      href={`https://wa.me/${WHATSAPP_NUMBER}`}
      target="_blank"
      rel="noreferrer"
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ delay: 0.6, type: "spring", stiffness: 200, damping: 15 }}
      whileHover={{ scale: 1.08 }}
      whileTap={{ scale: 0.95 }}
      className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-[#25D366] text-white shadow-lg"
      aria-label="Chat on WhatsApp"
    >
      <MessageCircle className="h-7 w-7" fill="white" />
    </motion.a>
  );
}

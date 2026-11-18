import { BASE } from "@/lib/salesImport";

export const AUTO_BASE = `${BASE}/automation`;
export const VERSIONS_BASE = `${BASE}/versions`;

export interface AutomationSettings {
  sheet_url: string | null;
  enabled: boolean;
  frequency: "daily" | "weekly" | "monthly";
  weekday: number;
  day_of_month: number;
  hour: number;
  period_from: string | null;
  period_to: string | null;
  auto_post: boolean;
  paused_reason: string | null;
  schedule_text: string;
  next_run_at: string | null;
  last_run_at: string | null;
  last_status: "imported" | "no_changes" | "failed" | null;
  last_message: string | null;
  consecutive_failures: number;
}

export interface AutomationRun {
  id: string;
  trigger: "scheduled" | "run_now";
  status: "imported" | "no_changes" | "failed";
  message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface AutomationState {
  settings: AutomationSettings;
  runs: AutomationRun[];
}

export interface Counts {
  new: number;
  updated: number;
  missing: number;
}

export interface ImportVersion {
  id: string;
  version_no: number;
  source: "manual" | "google_sheet" | "revert";
  filename: string | null;
  size_bytes: number;
  period_from: string | null;
  period_to: string | null;
  counts: { sales?: Counts; claims?: Counts; ipf?: Counts } | null;
  note: string | null;
  reverted_to_version_no: number | null;
  created_by_name: string | null;
  created_at: string | null;
  is_current: boolean;
}

export interface RevertPreview {
  version_no: number;
  counts: { sales?: Counts; claims?: Counts; ipf?: Counts };
  changes_total: number;
  changes: { client_name: string | null; policy_number: string | null; sheet: string | null; fields: unknown }[];
  missing_total: number;
  missing: { client_name: string | null; policy_number: string | null; sheet: string | null }[];
  posted_to_remove: number;
  will_pause_automation: boolean;
}

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function when(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString("en-KE", { timeZone: "Africa/Nairobi", dateStyle: "medium", timeStyle: "short" }) : "-";
}

export function sizeLabel(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export const SOURCE_LABEL: Record<ImportVersion["source"], string> = {
  manual: "Uploaded by hand",
  google_sheet: "Google Sheet",
  revert: "Reverted",
};

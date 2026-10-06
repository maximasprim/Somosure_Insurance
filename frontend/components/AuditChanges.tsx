"use client";

import type { AuditEntry } from "@/lib/types";

function show(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

/** Before/after table for one audit entry's field changes. */
export function AuditChanges({ changes }: { changes: AuditEntry["changes"] }) {
  const rows = Object.entries(changes ?? {});
  if (rows.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="text-ink-soft">
            <th className="py-1 pr-4 font-medium">Field</th>
            <th className="py-1 pr-4 font-medium">Before</th>
            <th className="py-1 font-medium">After</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([field, [before, after]]) => (
            <tr key={field} className="border-t border-neutral-border align-top">
              <td className="py-1 pr-4 font-mono text-ink">{field}</td>
              <td className="py-1 pr-4 text-ink-soft break-all">{show(before)}</td>
              <td className="py-1 text-ink break-all">{show(after)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

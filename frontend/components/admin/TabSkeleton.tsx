"use client";

/** What a tab shows while ALL of its data is on the way. Nothing real is drawn until everything has arrived, so a tab
 *  appears complete in one step instead of filling in piece by piece. Same footprint as a typical tab (a summary card, a
 *  row of figures and a table) so the page does not jump when the content replaces it. */
export function TabSkeleton() {
  const bar = "animate-pulse rounded-control bg-neutral";
  return (
    <div role="status" aria-busy="true" aria-live="polite" className="flex flex-col gap-4">
      <span className="sr-only">Loading…</span>
      <div className="rounded-card border border-neutral-border bg-white p-5">
        <div className={`${bar} h-6 w-1/3`} />
        <div className={`${bar} mt-3 h-4 w-full`} />
        <div className={`${bar} mt-2 h-4 w-5/6`} />
        <div className="mt-5 grid gap-3 md:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <div key={i} className={`${bar} h-20`} />)}
        </div>
      </div>
      <div className="rounded-card border border-neutral-border bg-white p-5">
        <div className={`${bar} h-5 w-1/4`} />
        <div className="mt-4 flex flex-col gap-3">
          {[0, 1, 2, 3, 4].map((i) => <div key={i} className={`${bar} h-8 w-full`} />)}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";

import type { ExcludedObligation } from "../types";

export function ExcludedSection({
  excluded,
  summary,
}: {
  excluded: ExcludedObligation[];
  summary: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="flex flex-col gap-2 rounded-md border border-ink/10">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center justify-between px-4 py-2 font-ui text-sm text-ink/70 hover:bg-ink/5"
      >
        <span>Excluded obligations ({excluded.length}) — considered and found not to apply</span>
        <span>{open ? "Hide" : "Show"}</span>
      </button>
      {open ? (
        <div className="flex flex-col gap-2 px-4 pb-3">
          <p className="font-document text-sm text-ink/70">{summary}</p>
          <ul className="flex flex-col gap-2">
            {excluded.map((item) => (
              <li key={item.predicate_id} className="border-t border-ink/10 pt-2">
                <p className="font-ui text-sm font-medium text-ink">{item.obligation_summary}</p>
                <p className="font-document text-xs text-ink/60">{item.rationale}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

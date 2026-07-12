"use client";

import { useState } from "react";

import { formatMoney } from "../format";
import type { MemoObligation } from "../types";
import { RangeBar } from "./RangeBar";

/**
 * One obligation's memo section: what it requires, why it applies, its
 * own cost range and timing, and a calculation-chain drawer — one click
 * (this card's own expand toggle) surfaces the clause references and
 * exact figures a headline number traces to.
 */
export function ObligationCard({ obligation }: { obligation: MemoObligation }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="flex flex-col gap-3 rounded-md border border-ink/10 p-4">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex items-center justify-between text-left"
      >
        <div className="flex flex-col">
          <span className="font-ui text-sm font-medium text-ink">
            {obligation.obligation_summary}
          </span>
          <span className="font-document text-xs text-ink/60">{obligation.what_it_requires}</span>
        </div>
        <span className="font-ui text-xs text-ink/50">{expanded ? "Hide detail" : "Detail"}</span>
      </button>

      <RangeBar
        low={obligation.impact_low}
        likely={obligation.impact_likely}
        high={obligation.impact_high}
        currency={obligation.currency}
      />

      {expanded ? (
        <div className="flex flex-col gap-3 rounded-md bg-ink/5 p-3">
          <div>
            <h4 className="font-ui text-xs font-medium uppercase tracking-wide text-ink/50">
              Why it applies
            </h4>
            <p className="font-document text-sm text-ink/80">{obligation.why_it_applies}</p>
            <p className="mt-1 font-ui text-xs text-ink/60">{obligation.rationale}</p>
          </div>

          <div>
            <h4 className="font-ui text-xs font-medium uppercase tracking-wide text-ink/50">
              Clause citations
            </h4>
            <ul className="flex flex-wrap gap-2">
              {obligation.clause_refs.map((ref) => (
                <li
                  key={ref}
                  className="rounded-full bg-ink/10 px-2 py-0.5 font-ui text-xs text-ink/70"
                >
                  {ref}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="font-ui text-xs font-medium uppercase tracking-wide text-ink/50">
              Timing (phased)
            </h4>
            <ul className="flex flex-col gap-1">
              {obligation.phased_schedule.map((entry) => (
                <li
                  key={entry.period}
                  className="flex justify-between font-ui text-xs tabular-nums text-ink/70"
                >
                  <span>{entry.period}</span>
                  <span>{formatMoney(entry.amount, obligation.currency)}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex justify-between font-ui text-xs text-ink/70">
            <span>Present value</span>
            <span className="tabular-nums">
              {formatMoney(obligation.present_value, obligation.currency)}
            </span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

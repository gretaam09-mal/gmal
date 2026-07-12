"use client";

import { useState } from "react";

import type { AnalysisItem } from "../types";
import { TriStateBadge } from "./TriStateBadge";

export function ExposureRow({
  item,
  fieldLabel,
  onNavigateToProfileField,
}: {
  item: AnalysisItem;
  fieldLabel: (key: string) => string;
  onNavigateToProfileField?: (fieldKey: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="flex flex-col gap-2 border-b border-ink/10 py-3 last:border-b-0">
      <div className="grid grid-cols-[1fr_120px_120px_120px_90px_110px] items-center gap-3">
        <div className="flex flex-col">
          <span className="font-ui text-sm font-medium text-ink">{item.instrument_title}</span>
          <span className="font-document text-xs text-ink/60">{item.obligation_summary}</span>
        </div>
        <TriStateBadge outcome={item.outcome} />
        <span className="font-ui text-xs tabular-nums text-ink/70">{item.impact_band}</span>
        <span className="font-ui text-xs tabular-nums text-ink/70">
          {item.first_obligation_date ?? "—"}
        </span>
        <span
          className="w-fit rounded-full bg-ink/5 px-2 py-0.5 font-ui text-xs tabular-nums text-ink/70"
          title="Extraction confidence"
        >
          {item.confidence}%
        </span>
        <span className="font-ui text-xs capitalize text-ink/50">
          {item.memo_status.replace(/_/g, " ")}
        </span>
      </div>

      {item.outcome === "ambiguous" && item.missing_field_keys.length > 0 ? (
        <p className="font-ui text-xs text-amber-800">
          Resolve by answering:{" "}
          {item.missing_field_keys.map((key, i) => (
            <span key={key}>
              {i > 0 ? ", " : ""}
              <button
                type="button"
                onClick={() => onNavigateToProfileField?.(key)}
                className="underline decoration-dotted hover:text-amber-900"
              >
                {fieldLabel(key)}
              </button>
            </span>
          ))}
        </p>
      ) : null}

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-fit font-ui text-xs text-ink/50 underline decoration-dotted hover:text-ink"
      >
        {expanded ? "Hide rationale" : "Why?"}
      </button>
      {expanded ? (
        <p className="rounded-md bg-ink/5 p-3 font-document text-sm text-ink/80">{item.rationale}</p>
      ) : null}
    </div>
  );
}

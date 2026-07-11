import { cn } from "@/lib/utils";

import type { FieldSource } from "../types";

const SOURCE_STYLES: Record<FieldSource, string> = {
  registry: "bg-primary-navy/10 text-primary-navy",
  filing: "bg-primary-navy/10 text-primary-navy",
  user: "bg-ink/10 text-ink",
  default: "bg-ink/5 text-ink/60",
  estimate: "bg-ink/5 text-ink/60",
  unknown: "bg-amber-100 text-amber-800",
};

const SOURCE_LABELS: Record<FieldSource, string> = {
  registry: "Registry",
  filing: "Filing",
  user: "Confirmed",
  default: "Default",
  estimate: "Estimate",
  unknown: "Unknown",
};

export function SourceBadge({ source }: { source: FieldSource }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 font-ui text-xs font-medium",
        SOURCE_STYLES[source],
      )}
    >
      {SOURCE_LABELS[source]}
    </span>
  );
}

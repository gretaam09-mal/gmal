import type { Outcome } from "../types";

const LABEL: Record<Outcome, string> = {
  binds: "Binds",
  does_not_bind: "Does not bind",
  ambiguous: "Ambiguous",
};

const STYLE: Record<Outcome, string> = {
  binds: "bg-emerald-100 text-emerald-800",
  does_not_bind: "bg-ink/10 text-ink/60",
  ambiguous: "bg-amber-100 text-amber-800",
};

export function TriStateBadge({ outcome }: { outcome: Outcome }) {
  return (
    <span className={`rounded-full px-2 py-0.5 font-ui text-xs font-medium ${STYLE[outcome]}`}>
      {LABEL[outcome]}
    </span>
  );
}

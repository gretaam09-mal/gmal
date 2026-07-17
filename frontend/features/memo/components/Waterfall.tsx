import { formatMoney } from "../format";
import type { MemoObligation } from "../types";

const SEGMENT_COLORS = [
  "bg-primary-navy",
  "bg-emerald-600",
  "bg-amber-600",
  "bg-sky-600",
  "bg-rose-600",
  "bg-violet-600",
];

/**
 * How the headline "likely" figure is composed from each binding
 * obligation's own likely cost — a single stacked bar, proportional
 * widths, with a legend underneath. Plain divs, no charting library.
 *
 * Legend labels use the instrument's short title (e.g. "Consumer Duty"),
 * not the obligation's full summary sentence — that fuller description
 * belongs to the Obligations section (ObligationCard) below; using it
 * here too would put the same sentence on screen twice.
 */
export function Waterfall({
  obligations,
  currency,
}: {
  obligations: MemoObligation[];
  currency: string;
}) {
  const total = obligations.reduce((sum, o) => sum + Number(o.impact_likely), 0) || 1;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex h-6 w-full overflow-hidden rounded-md">
        {obligations.map((obligation, index) => {
          const width = (Number(obligation.impact_likely) / total) * 100;
          return (
            <div
              key={obligation.predicate_id}
              className={SEGMENT_COLORS[index % SEGMENT_COLORS.length]}
              style={{ width: `${width}%` }}
              title={`${obligation.instrument_title}: ${formatMoney(obligation.impact_likely, currency)}`}
            />
          );
        })}
      </div>
      <ul className="flex flex-col gap-1">
        {obligations.map((obligation, index) => (
          <li key={obligation.predicate_id} className="flex items-center gap-2 font-ui text-xs">
            <span
              className={`h-2 w-2 shrink-0 rounded-full ${SEGMENT_COLORS[index % SEGMENT_COLORS.length]}`}
            />
            <span className="flex-1 text-ink/70">{obligation.instrument_title}</span>
            <span className="tabular-nums text-ink">
              {formatMoney(obligation.impact_likely, currency)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

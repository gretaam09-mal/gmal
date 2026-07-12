import { formatMoney } from "../format";

/**
 * Headline best/likely/worst range: a track spanning 0 -> worst, a
 * filled segment from best -> worst, and a marker at likely. Plain divs
 * (no charting library) — the shape is simple enough not to need one.
 */
export function RangeBar({
  low,
  likely,
  high,
  currency,
}: {
  low: string;
  likely: string;
  high: string;
  currency: string;
}) {
  const lowValue = Number(low);
  const likelyValue = Number(likely);
  const highValue = Number(high);
  const max = highValue > 0 ? highValue : 1;
  const lowPct = (lowValue / max) * 100;
  const likelyPct = (likelyValue / max) * 100;
  const highPct = 100;

  return (
    <div className="flex flex-col gap-2">
      <div className="relative h-3 w-full rounded-full bg-ink/5">
        <div
          className="absolute h-3 rounded-full bg-primary-navy/25"
          style={{ left: `${lowPct}%`, width: `${Math.max(highPct - lowPct, 1)}%` }}
        />
        <div
          className="absolute top-1/2 h-4 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary-navy"
          style={{ left: `${likelyPct}%` }}
          title={`Likely: ${formatMoney(likely, currency)}`}
        />
      </div>
      <div className="flex justify-between font-ui text-xs tabular-nums text-ink/70">
        <span>Best {formatMoney(low, currency)}</span>
        <span className="font-medium text-ink">Likely {formatMoney(likely, currency)}</span>
        <span>Worst {formatMoney(high, currency)}</span>
      </div>
    </div>
  );
}

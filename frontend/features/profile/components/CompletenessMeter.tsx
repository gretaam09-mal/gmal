import { SECTION_LABELS } from "../types";
import type { Completeness } from "../types";

export function CompletenessMeter({ completeness }: { completeness: Completeness }) {
  const percent = Math.round(completeness.overall_score * 100);

  return (
    <div className="flex flex-col gap-3 rounded-md border border-ink/10 p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-ui text-sm font-medium text-ink">Completeness</h3>
        <span className="font-ui text-sm tabular-nums text-ink">{percent}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-ink/10">
        <div className="h-full bg-primary-navy" style={{ width: `${percent}%` }} />
      </div>
      <ul className="flex flex-col gap-1">
        {completeness.sections.map((section) => (
          <li key={section.section} className="flex items-center justify-between font-ui text-xs">
            <span className="text-ink/60">{SECTION_LABELS[section.section]}</span>
            <span className="tabular-nums text-ink/60">{Math.round(section.score * 100)}%</span>
          </li>
        ))}
      </ul>
      {completeness.unknown_field_labels.length > 0 ? (
        <p className="font-ui text-xs text-amber-700">
          Unknown will reduce memo confidence for: {completeness.unknown_field_labels.join(", ")}
        </p>
      ) : null}
    </div>
  );
}

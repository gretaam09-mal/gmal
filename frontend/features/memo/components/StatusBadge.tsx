import type { MemoStatus } from "../types";

const LABEL: Record<MemoStatus, string> = {
  draft: "Draft",
  in_review: "In review",
  approved: "Approved",
};

const STYLE: Record<MemoStatus, string> = {
  draft: "bg-ink/10 text-ink/70",
  in_review: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
};

export function StatusBadge({ status }: { status: MemoStatus }) {
  return (
    <span className={`rounded-full px-2 py-0.5 font-ui text-xs font-medium ${STYLE[status]}`}>
      {LABEL[status]}
    </span>
  );
}

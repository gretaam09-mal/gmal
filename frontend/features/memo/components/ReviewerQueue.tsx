"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";

import { getReviewQueue } from "../api";
import type { ReviewQueueEntry } from "../types";
import { StatusBadge } from "./StatusBadge";

export function ReviewerQueue({
  workspaceId,
  onSelectMemo,
}: {
  workspaceId: string;
  onSelectMemo?: (memoId: string) => void;
}) {
  const { getToken } = useAuth();
  const [entries, setEntries] = useState<ReviewQueueEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getReviewQueue(getToken, workspaceId)
      .then(setEntries)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load queue"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  if (loading) {
    return <p className="font-ui text-sm text-ink/60">Loading review queue…</p>;
  }

  if (error) {
    return <p className="font-ui text-xs text-red-600">{error}</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="font-ui text-lg font-semibold text-ink">Reviewer queue</h2>
      <p className="font-ui text-sm text-ink/60">
        Draft and in-review memos, low-confidence and ambiguity-heavy ones first.
      </p>
      {entries.length === 0 ? (
        <p className="font-ui text-sm text-ink/50">Nothing waiting for review.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {entries.map((entry) => (
            <li key={entry.version_id}>
              <button
                type="button"
                onClick={() => onSelectMemo?.(entry.memo_id)}
                className="flex w-full items-center justify-between rounded-md border border-ink/10 px-3 py-2 text-left hover:bg-ink/5"
              >
                <div className="flex flex-col">
                  <span className="font-ui text-sm text-ink">{entry.memo_title}</span>
                  <span className="font-ui text-xs text-ink/50">
                    Version {entry.version_number}
                    {entry.confidence_grade ? ` · Grade ${entry.confidence_grade}` : " · No grade"}
                    {entry.ambiguous_count > 0
                      ? ` · ${entry.ambiguous_count} ambiguous`
                      : ""}
                  </span>
                </div>
                <StatusBadge status={entry.status} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

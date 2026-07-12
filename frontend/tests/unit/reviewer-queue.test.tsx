import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReviewerQueue } from "@/features/memo/components/ReviewerQueue";
import type { ReviewQueueEntry } from "@/features/memo/types";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token" }),
}));

const getReviewQueue = vi.fn();
vi.mock("../../features/memo/api", () => ({
  getReviewQueue: (...args: unknown[]) => getReviewQueue(...args),
}));

function makeEntry(overrides: Partial<ReviewQueueEntry> = {}): ReviewQueueEntry {
  return {
    memo_id: "memo-1",
    memo_title: "Project Falcon — Impact Memo",
    version_id: "version-1",
    version_number: 1,
    status: "in_review",
    confidence_grade: "C",
    ambiguous_count: 2,
    submitted_at: "2027-01-01T00:00:00Z",
    created_at: "2027-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("ReviewerQueue", () => {
  it("shows queue entries with grade and ambiguity count", async () => {
    getReviewQueue.mockResolvedValueOnce([makeEntry()]);
    render(<ReviewerQueue workspaceId="workspace-1" />);

    await waitFor(() => expect(screen.getByText("Project Falcon — Impact Memo")).toBeInTheDocument());
    expect(screen.getByText(/Grade C/)).toBeInTheDocument();
    expect(screen.getByText(/2 ambiguous/)).toBeInTheDocument();
  });

  it("shows an empty state when nothing needs review", async () => {
    getReviewQueue.mockResolvedValueOnce([]);
    render(<ReviewerQueue workspaceId="workspace-1" />);

    await waitFor(() =>
      expect(screen.getByText("Nothing waiting for review.")).toBeInTheDocument(),
    );
  });

  it("calls onSelectMemo when a queue entry is clicked", async () => {
    getReviewQueue.mockResolvedValueOnce([makeEntry()]);
    const onSelectMemo = vi.fn();
    render(<ReviewerQueue workspaceId="workspace-1" onSelectMemo={onSelectMemo} />);

    await waitFor(() => screen.getByText("Project Falcon — Impact Memo"));
    fireEvent.click(screen.getByText("Project Falcon — Impact Memo"));
    expect(onSelectMemo).toHaveBeenCalledWith("memo-1");
  });
});

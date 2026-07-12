import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MonthlyMetricsView } from "@/features/admin/components/MonthlyMetricsView";
import type { MonthlyMetricsReport } from "@/features/admin/types";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token" }),
}));

const getMonthlyMetricsReport = vi.fn();
vi.mock("../../features/admin/api", () => ({
  getMonthlyMetricsReport: (...args: unknown[]) => getMonthlyMetricsReport(...args),
}));

function makeReport(overrides: Partial<MonthlyMetricsReport> = {}): MonthlyMetricsReport {
  return {
    period_start: "2027-03-01T00:00:00Z",
    period_end: "2027-04-01T00:00:00Z",
    time_to_exposure_list_minutes_avg: 120,
    time_to_approved_memo_minutes_avg: 90,
    review_minutes_avg: 45,
    onboarding_hours_avg: 3.5,
    override_count: 4,
    memos_approved_count: 6,
    used_in_ic_count: 2,
    ...overrides,
  };
}

describe("MonthlyMetricsView", () => {
  it("renders every board metric from the report", async () => {
    getMonthlyMetricsReport.mockResolvedValueOnce(makeReport());
    render(<MonthlyMetricsView />);

    await waitFor(() => expect(screen.getByText("120.0 min")).toBeInTheDocument());
    expect(screen.getByText("90.0 min")).toBeInTheDocument();
    expect(screen.getByText("45.0 min")).toBeInTheDocument();
    expect(screen.getByText("3.5 hrs")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("renders a dash for metrics with no data yet", async () => {
    getMonthlyMetricsReport.mockResolvedValueOnce(
      makeReport({
        time_to_exposure_list_minutes_avg: null,
        time_to_approved_memo_minutes_avg: null,
        review_minutes_avg: null,
        onboarding_hours_avg: null,
      }),
    );
    render(<MonthlyMetricsView />);

    await waitFor(() => expect(screen.getAllByText("—").length).toBeGreaterThan(0));
  });
});

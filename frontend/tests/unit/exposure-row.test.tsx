import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ExposureRow } from "@/features/exposure/components/ExposureRow";
import type { AnalysisItem } from "@/features/exposure/types";

function makeItem(overrides: Partial<AnalysisItem> = {}): AnalysisItem {
  return {
    id: "item-1",
    predicate_id: "pred-1",
    instrument_title: "Sample Data Protection Act",
    obligation_summary: "Appoint a data protection officer.",
    outcome: "binds",
    missing_field_keys: [],
    rationale: "Binds: Appoint a data protection officer.",
    clause_refs: ["s.1"],
    amount: 9000,
    currency: "GBP",
    impact_band: "< £10k",
    confidence: 88,
    first_obligation_date: "2026-01-01",
    memo_status: "not_started",
    engine_version: "1",
    computed_at: "2026-07-12T00:00:00Z",
    ...overrides,
  };
}

describe("ExposureRow", () => {
  it("shows the rationale only after clicking 'Why?'", () => {
    render(<ExposureRow item={makeItem()} fieldLabel={(k) => k} />);
    expect(screen.queryByText(/Appoint a data protection officer\./, { selector: "p" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Why?"));
    expect(screen.getByText(makeItem().rationale)).toBeInTheDocument();
  });

  it("lets an ambiguous row deep-link to the missing profile field", () => {
    const onNavigate = vi.fn();
    const item = makeItem({
      outcome: "ambiguous",
      missing_field_keys: ["footprint.processes_personal_data"],
    });
    render(
      <ExposureRow
        item={item}
        fieldLabel={(key) => (key === "footprint.processes_personal_data" ? "Processes personal data?" : key)}
        onNavigateToProfileField={onNavigate}
      />,
    );

    fireEvent.click(screen.getByText("Processes personal data?"));
    expect(onNavigate).toHaveBeenCalledWith("footprint.processes_personal_data");
  });

  it("does not show a resolve-by prompt for a binds row", () => {
    render(<ExposureRow item={makeItem()} fieldLabel={(k) => k} />);
    expect(screen.queryByText(/Resolve by answering/)).not.toBeInTheDocument();
  });
});

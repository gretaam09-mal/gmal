import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ObligationCard } from "@/features/memo/components/ObligationCard";
import type { MemoObligation } from "@/features/memo/types";

function makeObligation(overrides: Partial<MemoObligation> = {}): MemoObligation {
  return {
    predicate_id: "pred-1",
    instrument_title: "Test Data Protection Act",
    obligation_summary: "Appoint a data protection officer.",
    clause_refs: ["s.1"],
    rationale: "Binds: processes personal data.",
    impact_low: "20000.00",
    impact_likely: "25000.00",
    impact_high: "32500.00",
    currency: "GBP",
    phased_schedule: [{ period: "2027-01", amount: "25000.00" }],
    present_value: "24000.00",
    what_it_requires: "The firm must appoint a suitably qualified DPO.",
    why_it_applies: "The target processes personal data at scale.",
    ...overrides,
  };
}

describe("ObligationCard", () => {
  it("shows the range bar and summary without expanding", () => {
    render(<ObligationCard obligation={makeObligation()} />);
    expect(screen.getByText("Appoint a data protection officer.")).toBeInTheDocument();
    expect(screen.queryByText("s.1")).not.toBeInTheDocument();
  });

  it("surfaces clause citations and the calculation chain in one click", () => {
    render(<ObligationCard obligation={makeObligation()} />);
    fireEvent.click(screen.getByText("Detail"));

    expect(screen.getByText("s.1")).toBeInTheDocument();
    expect(screen.getByText("2027-01")).toBeInTheDocument();
    expect(screen.getByText("The target processes personal data at scale.")).toBeInTheDocument();
  });

  it("does not repeat the summary as a subtitle before expanding — only after", () => {
    render(<ObligationCard obligation={makeObligation()} />);
    expect(
      screen.queryByText("The firm must appoint a suitably qualified DPO.")
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Detail"));
    expect(screen.getByText("The firm must appoint a suitably qualified DPO.")).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ObligationPanel } from "@/features/admin/components/ObligationPanel";
import type { Clause, Obligation } from "@/features/admin/types";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: async () => "test-token" }),
}));

vi.mock("../../features/admin/api", () => ({
  listObligationPredicates: vi.fn().mockResolvedValue([]),
  updateObligation: vi.fn(),
  approveObligation: vi.fn(),
  createPredicate: vi.fn(),
  draftPredicate: vi.fn(),
  testPredicate: vi.fn(),
  updatePredicate: vi.fn(),
  approvePredicate: vi.fn(),
  attachCostTemplate: vi.fn(),
  getObligationCostTemplate: vi.fn().mockResolvedValue(null),
}));

function makeClause(): Clause {
  return { id: "clause-1", clause_ref: "s.1", text: "A firm must appoint a DPO.", ordinal: 1 };
}

function makeObligation(overrides: Partial<Obligation> = {}): Obligation {
  return {
    id: "obligation-1",
    clause_id: "clause-1",
    summary: "Appoint a data protection officer.",
    obligation_type: "appointment",
    fields: {
      who: { value: "firms processing personal data", clause_ref: "s.1", confidence: 92 },
      what: { value: "appoint a DPO", clause_ref: "s.1", confidence: 95 },
      when: { value: "not specified in this clause", clause_ref: "s.1", confidence: 30 },
      threshold: { value: "processes personal data at scale", clause_ref: "s.1", confidence: 88 },
      enforcer: { value: "the ICO", clause_ref: "s.1", confidence: 55 },
    },
    confidence: 72,
    extracted_by: "P-EXTRACT",
    approved: false,
    approved_by_user_id: null,
    approved_at: null,
    ...overrides,
  };
}

describe("ObligationPanel", () => {
  it("surfaces the lowest-confidence field first and flags it, per FR-7", () => {
    render(
      <ObligationPanel clause={makeClause()} obligation={makeObligation()} onObligationChange={vi.fn()} />
    );

    const labels = screen
      .getAllByText(/^(Who|What|When|Threshold|Enforcer)$/)
      .map((el) => el.textContent);
    // "when" (30%) and "enforcer" (55%) are below the 70% threshold; "when"
    // is the least confident field and must come first.
    expect(labels[0]).toBe("When");
    expect(labels[1]).toBe("Enforcer");

    expect(screen.getByText(/2 fields are below 70% confidence/)).toBeInTheDocument();
    expect(screen.getAllByText(/— check this/).length).toBe(2);
  });

  it("keeps the canonical field order for an already-approved obligation", () => {
    render(
      <ObligationPanel
        clause={makeClause()}
        obligation={makeObligation({ approved: true, approved_by_user_id: "user-1" })}
        onObligationChange={vi.fn()}
      />
    );

    const labels = screen
      .getAllByText(/^(Who|What|When|Threshold|Enforcer)$/)
      .map((el) => el.textContent);
    expect(labels).toEqual(["Who", "What", "When", "Threshold", "Enforcer"]);
    expect(screen.queryByText(/fields are below/)).not.toBeInTheDocument();
  });
});

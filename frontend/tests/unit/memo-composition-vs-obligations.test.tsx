/**
 * Reproduces the actual reported bug: the Composition-of-the-range
 * legend (Waterfall) and the Obligations section heading (ObligationCard)
 * showed the exact same obligation_summary sentence, verbatim, in two
 * places on the same rendered memo. A prior fix only touched
 * ObligationCard's own internal layout (see obligation-card.test.tsx) and
 * never rendered Waterfall and ObligationCard side by side against the
 * same obligation object — so it never actually caught this. This test
 * renders both real components together, from one shared obligation
 * (the same shape MemoView passes to both), and asserts the two visible
 * texts are not identical and don't leak into each other's component.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ObligationCard } from "@/features/memo/components/ObligationCard";
import { Waterfall } from "@/features/memo/components/Waterfall";
import type { MemoObligation } from "@/features/memo/types";

const obligation: MemoObligation = {
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
  cost_source: "expert_template",
  cost_rationale: null,
  cost_assumptions: null,
  cost_drivers: null,
};

describe("Composition of the range vs. Obligations section", () => {
  it("show different text for the same obligation, not the same sentence twice", () => {
    const { container: compositionContainer } = render(
      <Waterfall obligations={[obligation]} currency="GBP" />
    );
    const { container: obligationsContainer } = render(<ObligationCard obligation={obligation} />);

    const compositionText = within(compositionContainer).getByText(obligation.instrument_title);
    const obligationsHeading = within(obligationsContainer).getByText(
      obligation.obligation_summary
    );

    // The real bug: both used to render obligation.obligation_summary,
    // so this would have been the identical string in both places.
    expect(compositionText.textContent).not.toBe(obligationsHeading.textContent);
    expect(obligation.instrument_title).not.toBe(obligation.obligation_summary);
  });

  it("does not put the Obligations heading text in the Composition legend", () => {
    render(<Waterfall obligations={[obligation]} currency="GBP" />);
    expect(screen.queryByText(obligation.obligation_summary)).not.toBeInTheDocument();
    expect(screen.getByText(obligation.instrument_title)).toBeInTheDocument();
  });

  it("does not put the Composition legend text in the Obligations heading", () => {
    render(<ObligationCard obligation={obligation} />);
    expect(screen.queryByText(obligation.instrument_title)).not.toBeInTheDocument();
    expect(screen.getByText(obligation.obligation_summary)).toBeInTheDocument();
  });
});

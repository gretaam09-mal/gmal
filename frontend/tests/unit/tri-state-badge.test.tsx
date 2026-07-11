import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TriStateBadge } from "@/features/exposure/components/TriStateBadge";

describe("TriStateBadge", () => {
  it("renders a human label for each outcome", () => {
    const { rerender } = render(<TriStateBadge outcome="binds" />);
    expect(screen.getByText("Binds")).toBeInTheDocument();

    rerender(<TriStateBadge outcome="does_not_bind" />);
    expect(screen.getByText("Does not bind")).toBeInTheDocument();

    rerender(<TriStateBadge outcome="ambiguous" />);
    expect(screen.getByText("Ambiguous")).toBeInTheDocument();
  });
});

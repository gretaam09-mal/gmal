import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/features/memo/components/StatusBadge";

describe("StatusBadge", () => {
  it("renders a human label for each memo status", () => {
    const { rerender } = render(<StatusBadge status="draft" />);
    expect(screen.getByText("Draft")).toBeInTheDocument();

    rerender(<StatusBadge status="in_review" />);
    expect(screen.getByText("In review")).toBeInTheDocument();

    rerender(<StatusBadge status="approved" />);
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });
});

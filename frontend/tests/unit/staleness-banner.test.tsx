import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StalenessBanner } from "@/features/memo/components/StalenessBanner";

describe("StalenessBanner", () => {
  it("renders nothing when there are no stale reasons", () => {
    const { container } = render(<StalenessBanner reasons={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists every reason an instrument version changed underneath the memo", () => {
    render(
      <StalenessBanner
        reasons={[
          "Test Data Protection Act was updated to version v2; this memo used the superseded version.",
        ]}
      />,
    );
    expect(screen.getByText("Inputs changed")).toBeInTheDocument();
    expect(screen.getByText(/Test Data Protection Act was updated/)).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "@/design-system/components/button";

describe("Button", () => {
  it("renders its children", () => {
    render(<Button>Continue</Button>);
    expect(screen.getByRole("button", { name: "Continue" })).toBeInTheDocument();
  });
});

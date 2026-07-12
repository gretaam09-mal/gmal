import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AssumptionRegister } from "@/features/memo/components/AssumptionRegister";
import type { Assumption } from "@/features/memo/types";

function makeAssumption(overrides: Partial<Assumption> = {}): Assumption {
  return {
    id: "assumption-1",
    key: "driver:pred-1:scale.employee_count",
    value: { value: "500" },
    source: "profile_field:scale.employee_count",
    note: null,
    ...overrides,
  };
}

describe("AssumptionRegister", () => {
  it("does not show an override control when the caller cannot edit", () => {
    render(
      <AssumptionRegister assumptions={[makeAssumption()]} canEdit={false} onOverride={vi.fn()} />,
    );
    expect(screen.queryByText("Override")).not.toBeInTheDocument();
  });

  it("lets an editor override a value and calls onOverride with the new value and note", async () => {
    const onOverride = vi.fn().mockResolvedValue(undefined);
    render(
      <AssumptionRegister assumptions={[makeAssumption()]} canEdit={true} onOverride={onOverride} />,
    );

    fireEvent.click(screen.getByText("Override"));
    const valueInput = screen.getByDisplayValue("500");
    fireEvent.change(valueInput, { target: { value: "1000" } });
    const noteInput = screen.getByPlaceholderText("Why this override?");
    fireEvent.change(noteInput, { target: { value: "Updated headcount" } });
    fireEvent.click(screen.getByText("Save"));

    expect(onOverride).toHaveBeenCalledWith(makeAssumption(), "1000", "Updated headcount");
  });

  it("does not offer an override control for a non-scalar assumption value", () => {
    render(
      <AssumptionRegister
        assumptions={[makeAssumption({ value: { formula: { base: 5000 } } })]}
        canEdit={true}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.queryByText("Override")).not.toBeInTheDocument();
  });
});

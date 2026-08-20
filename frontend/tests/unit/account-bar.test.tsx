import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccountBar } from "@/features/shared/components/AccountBar";

const signOut = vi.fn();
vi.mock("@clerk/nextjs", () => ({
  useClerk: () => ({ signOut }),
  useUser: () => ({ user: { primaryEmailAddress: { emailAddress: "owner@example.com" } } }),
}));

describe("AccountBar", () => {
  it("shows the signed-in email and signs out on click", () => {
    render(<AccountBar isStaff={false} />);

    expect(screen.getByText("owner@example.com")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(signOut).toHaveBeenCalledWith({ redirectUrl: "/" });
  });

  it("shows a link to the workbench only for staff accounts", () => {
    const { rerender } = render(<AccountBar isStaff={false} />);
    expect(screen.queryByRole("link", { name: "Instrument workbench" })).not.toBeInTheDocument();

    rerender(<AccountBar isStaff />);
    const link = screen.getByRole("link", { name: "Instrument workbench" });
    expect(link).toHaveAttribute("href", "/admin");
  });
});

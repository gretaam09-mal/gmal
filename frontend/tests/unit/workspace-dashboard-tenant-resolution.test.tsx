/**
 * Reproduces the actual reported bug: "my assessments keep disappearing
 * from the dashboard". The old WorkspaceDashboard trusted a tenant id
 * cached in localStorage as its ONLY record of "which organisation is
 * mine" — nothing server-side. A cleared browser (exactly what a test
 * render starts as, with no localStorage set) landed on "Set up your
 * organisation" even when the account already had one, offering to
 * create a brand new, empty tenant right on top of the real one.
 *
 * These tests render the real component against a mocked API layer and
 * assert it now asks the backend (GET /tenants, via listMyTenants) before
 * ever showing the "create an organisation" prompt.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceDashboard } from "@/features/workspaces/components/WorkspaceDashboard";
import type { Tenant, Workspace } from "@/features/workspaces/types";

// A stable reference (not a fresh closure per render) — mirrors the real
// @clerk/nextjs useAuth(), whose getToken is memoized, so effects that
// depend on it don't re-fire on every render the way an inline arrow
// returned from the mock would.
const getTokenMock = async () => "test-token";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: getTokenMock }),
  useClerk: () => ({ signOut: vi.fn() }),
  useUser: () => ({ user: { primaryEmailAddress: { emailAddress: "gretaam09@gmail.com" } } }),
}));

vi.mock("../../lib/me", () => ({
  getMe: vi.fn().mockResolvedValue({
    id: "user-1",
    email: "gretaam09@gmail.com",
    is_staff: false,
    admin_emails_configured: false,
    email_matches_admin_list: false,
  }),
}));

const listMyTenants = vi.fn();
const listWorkspaces = vi.fn();
const createTenant = vi.fn();
const createWorkspace = vi.fn();
vi.mock("../../features/workspaces/api", () => ({
  listMyTenants: (...args: unknown[]) => listMyTenants(...args),
  listWorkspaces: (...args: unknown[]) => listWorkspaces(...args),
  createTenant: (...args: unknown[]) => createTenant(...args),
  createWorkspace: (...args: unknown[]) => createWorkspace(...args),
}));

function makeTenant(overrides: Partial<Tenant> = {}): Tenant {
  return {
    id: "tenant-1",
    name: "Project Falcon Fund",
    slug: "project-falcon-fund",
    created_at: "2027-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeWorkspace(overrides: Partial<Workspace> = {}): Workspace {
  return {
    id: "workspace-1",
    tenant_id: "tenant-1",
    codename: "project-falcon",
    real_name: null,
    created_at: "2027-01-01T00:00:00Z",
    my_role: "owner",
    ...overrides,
  };
}

describe("WorkspaceDashboard tenant resolution", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the existing organisation's assessments instead of 'create an organisation' when the backend has one, even with no localStorage", async () => {
    window.localStorage.clear();
    listMyTenants.mockResolvedValue([makeTenant()]);
    listWorkspaces.mockResolvedValue([makeWorkspace()]);

    render(<WorkspaceDashboard />);

    await waitFor(() => expect(screen.getByText("project-falcon")).toBeInTheDocument());
    expect(screen.queryByText("Set up your organisation")).not.toBeInTheDocument();
  });

  it("only offers to create an organisation when the backend genuinely has none for this identity", async () => {
    window.localStorage.clear();
    listMyTenants.mockResolvedValue([]);

    render(<WorkspaceDashboard />);

    await waitFor(() => expect(screen.getByText("Set up your organisation")).toBeInTheDocument());
  });

  it("resolves the same tenant regardless of a stale or missing localStorage value", async () => {
    // Simulates a cleared browser / new device: nothing cached locally,
    // yet the account's real tenant is still reachable via the backend.
    window.localStorage.removeItem("provision:lastTenantId");
    listMyTenants.mockResolvedValue([makeTenant({ id: "tenant-real", name: "Real Fund" })]);
    listWorkspaces.mockResolvedValue([
      makeWorkspace({ tenant_id: "tenant-real", codename: "project-osprey" }),
    ]);

    render(<WorkspaceDashboard />);

    await waitFor(() => expect(listWorkspaces).toHaveBeenCalledWith(expect.anything(), "tenant-real"));
    expect(screen.getByText("project-osprey")).toBeInTheDocument();
  });

  it("lists every tenant the identity belongs to so duplicates from the old bug are all reachable, not just one", async () => {
    window.localStorage.clear();
    listMyTenants.mockResolvedValue([
      makeTenant({ id: "tenant-1", name: "First Fund" }),
      makeTenant({ id: "tenant-2", name: "Second Fund (orphaned before the fix)" }),
    ]);
    listWorkspaces.mockResolvedValue([]);

    render(<WorkspaceDashboard />);

    await waitFor(() => expect(screen.getByText("First Fund")).toBeInTheDocument());
    expect(screen.getByText("Second Fund (orphaned before the fix)")).toBeInTheDocument();
  });
});

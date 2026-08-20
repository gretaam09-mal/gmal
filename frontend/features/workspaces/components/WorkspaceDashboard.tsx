"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";

import { Button } from "@/design-system/components/button";
import { ExposureList } from "@/features/exposure";
import { MemoView, ReviewerQueue } from "@/features/memo";
import { ProfileEditor } from "@/features/profile/components/ProfileEditor";
import { AccountBar } from "@/features/shared/components/AccountBar";
import { getMe } from "@/lib/me";

import { createTenant, createWorkspace, listMyTenants, listWorkspaces } from "../api";
import type { Tenant, Workspace } from "../types";
import { MembersPanel } from "./MembersPanel";
import { RoleBadge } from "./RoleBadge";

const LAST_TENANT_KEY = "provision:lastTenantId";
type Tab = "profile" | "exposure" | "memo" | "review" | "members";

export function WorkspaceDashboard() {
  const { getToken } = useAuth();
  const [tenants, setTenants] = useState<Tenant[] | null>(null); // null = still loading
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("profile");
  const [isStaff, setIsStaff] = useState(false);

  useEffect(() => {
    // The database — not the browser's localStorage — is the source of
    // truth for which organisation(s) this Clerk identity belongs to.
    // A cleared browser or a new device used to lose the cached tenant id
    // entirely and land here as if the user had never created anything;
    // this always re-discovers every organisation the user actually has a
    // claim on (see GET /tenants) before ever offering "create one".
    listMyTenants(getToken).then((myTenants) => {
      setTenants(myTenants);
      if (myTenants.length === 0) return;
      const stored = typeof window !== "undefined" ? window.localStorage.getItem(LAST_TENANT_KEY) : null;
      const resolved = myTenants.find((t) => t.id === stored) ?? myTenants[0];
      if (!resolved) return;
      setTenantId(resolved.id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    getMe(getToken)
      .then((me) => setIsStaff(me.is_staff))
      .catch(() => setIsStaff(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!tenantId) return;
    if (typeof window !== "undefined") window.localStorage.setItem(LAST_TENANT_KEY, tenantId);
    listWorkspaces(getToken, tenantId).then(setWorkspaces);
  }, [tenantId, getToken]);

  async function handleCreateTenant(name: string, slug: string) {
    const tenant = await createTenant(getToken, { name, slug });
    setTenants((prev) => [...(prev ?? []), tenant]);
    setTenantId(tenant.id);
  }

  function handleSwitchTenant(id: string) {
    setSelectedWorkspaceId(null);
    setTenantId(id);
  }

  async function handleCreateWorkspace(codename: string, realName: string) {
    if (!tenantId) return;
    const workspace = await createWorkspace(getToken, tenantId, {
      codename,
      real_name: realName || undefined,
    });
    setWorkspaces((prev) => [...prev, workspace]);
    setSelectedWorkspaceId(workspace.id);
  }

  const selectedWorkspace = workspaces.find((w) => w.id === selectedWorkspaceId) ?? null;

  return (
    <div className="flex min-h-screen flex-col gap-6 p-8">
      <header className="flex items-center justify-between">
        <h1 className="font-ui text-2xl font-semibold text-ink">Provision</h1>
        <AccountBar isStaff={isStaff} />
      </header>

      {tenants === null ? (
        <p className="font-ui text-sm text-ink/60">Loading your organisations…</p>
      ) : tenants.length === 0 ? (
        <CreateTenantForm onCreate={handleCreateTenant} />
      ) : !tenantId ? null : (
        <div className="grid grid-cols-[240px_1fr] gap-6">
          <aside className="flex flex-col gap-4">
            {tenants.length > 1 ? (
              <div className="flex flex-col gap-1">
                <h2 className="font-ui text-sm font-medium uppercase tracking-wide text-ink/50">
                  Organisation
                </h2>
                <select
                  value={tenantId}
                  onChange={(event) => handleSwitchTenant(event.target.value)}
                  className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
                >
                  {tenants.map((tenant) => (
                    <option key={tenant.id} value={tenant.id}>
                      {tenant.name}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
            <h2 className="font-ui text-sm font-medium uppercase tracking-wide text-ink/50">
              Assessments
            </h2>
            <ul className="flex flex-col gap-1">
              {workspaces.map((workspace) => (
                <li key={workspace.id}>
                  <button
                    onClick={() => setSelectedWorkspaceId(workspace.id)}
                    className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left font-ui text-sm ${
                      workspace.id === selectedWorkspaceId ? "bg-ink/10" : "hover:bg-ink/5"
                    }`}
                  >
                    <span>{workspace.codename}</span>
                    {workspace.my_role ? <RoleBadge role={workspace.my_role} /> : null}
                  </button>
                </li>
              ))}
            </ul>
            <CreateWorkspaceForm onCreate={handleCreateWorkspace} />
          </aside>

          <main>
            {selectedWorkspace ? (
              <div className="flex flex-col gap-6">
                <div>
                  <h2 className="font-ui text-xl font-semibold text-ink">
                    {selectedWorkspace.codename}
                  </h2>
                  {selectedWorkspace.real_name ? (
                    <p className="font-ui text-sm text-ink/50">
                      Subject company: {selectedWorkspace.real_name}
                    </p>
                  ) : null}
                </div>

                <div className="flex gap-4 border-b border-ink/10">
                  {(["profile", "exposure", "memo", "review", "members"] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`pb-2 font-ui text-sm capitalize ${
                        tab === activeTab
                          ? "border-b-2 border-primary-navy text-ink"
                          : "text-ink/50 hover:text-ink"
                      }`}
                    >
                      {tab}
                    </button>
                  ))}
                </div>

                {activeTab === "profile" ? (
                  <ProfileEditor workspaceId={selectedWorkspace.id} />
                ) : activeTab === "exposure" ? (
                  <ExposureList
                    workspaceId={selectedWorkspace.id}
                    onNavigateToProfileField={() => setActiveTab("profile")}
                  />
                ) : activeTab === "memo" ? (
                  <MemoView workspaceId={selectedWorkspace.id} myRole={selectedWorkspace.my_role} />
                ) : activeTab === "review" ? (
                  <ReviewerQueue
                    workspaceId={selectedWorkspace.id}
                    onSelectMemo={() => setActiveTab("memo")}
                  />
                ) : (
                  <MembersPanel workspace={selectedWorkspace} getToken={getToken} />
                )}
              </div>
            ) : (
              <p className="font-ui text-sm text-ink/60">
                Select or create an assessment to get started.
              </p>
            )}
          </main>
        </div>
      )}
    </div>
  );
}

function CreateTenantForm({ onCreate }: { onCreate: (name: string, slug: string) => void }) {
  const [name, setName] = useState("");

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8">
      <h1 className="font-ui text-xl font-semibold text-ink">Set up your organisation</h1>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const slug = name
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "");
          onCreate(name, slug || `organisation-${Date.now()}`);
        }}
        className="flex flex-col gap-2"
      >
        <input
          required
          placeholder="Organisation name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="rounded border border-ink/20 bg-paper px-3 py-2 font-ui text-sm"
        />
        <Button type="submit">Create organisation</Button>
      </form>
    </div>
  );
}

function CreateWorkspaceForm({
  onCreate,
}: {
  onCreate: (codename: string, realName: string) => void;
}) {
  const [codename, setCodename] = useState("");
  const [realName, setRealName] = useState("");

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onCreate(codename, realName);
        setCodename("");
        setRealName("");
      }}
      className="flex flex-col gap-2 rounded-md border border-ink/10 p-3"
    >
      <h3 className="font-ui text-sm font-medium text-ink">New assessment</h3>
      <input
        required
        placeholder="Assessment name"
        value={codename}
        onChange={(event) => setCodename(event.target.value)}
        className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
      />
      <input
        placeholder="Subject company (optional)"
        value={realName}
        onChange={(event) => setRealName(event.target.value)}
        className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
      />
      <Button type="submit" size="dense">
        Create
      </Button>
    </form>
  );
}

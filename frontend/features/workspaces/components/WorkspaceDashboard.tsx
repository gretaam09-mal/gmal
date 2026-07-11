"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";

import { Button } from "@/design-system/components/button";

import { createTenant, createWorkspace, listWorkspaces } from "../api";
import type { Workspace } from "../types";
import { MembersPanel } from "./MembersPanel";
import { RoleBadge } from "./RoleBadge";

const LAST_TENANT_KEY = "provision:lastTenantId";

export function WorkspaceDashboard() {
  const { getToken } = useAuth();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem(LAST_TENANT_KEY) : null;
    if (stored) setTenantId(stored);
  }, []);

  useEffect(() => {
    if (!tenantId) return;
    listWorkspaces(getToken, tenantId).then(setWorkspaces);
  }, [tenantId, getToken]);

  async function handleCreateTenant(name: string, slug: string) {
    const tenant = await createTenant(getToken, { name, slug });
    window.localStorage.setItem(LAST_TENANT_KEY, tenant.id);
    setTenantId(tenant.id);
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

  if (!tenantId) {
    return <CreateTenantForm onCreate={handleCreateTenant} />;
  }

  const selectedWorkspace = workspaces.find((w) => w.id === selectedWorkspaceId) ?? null;

  return (
    <div className="flex min-h-screen flex-col gap-6 p-8">
      <header className="flex items-center justify-between">
        <h1 className="font-ui text-2xl font-semibold text-ink">Provision</h1>
      </header>

      <div className="grid grid-cols-[240px_1fr] gap-6">
        <aside className="flex flex-col gap-4">
          <h2 className="font-ui text-sm font-medium uppercase tracking-wide text-ink/50">
            Workspaces
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
                  {selectedWorkspace.real_name ?? selectedWorkspace.codename}
                </h2>
                {selectedWorkspace.real_name ? (
                  <p className="font-ui text-sm text-ink/50">codename: {selectedWorkspace.codename}</p>
                ) : null}
              </div>
              <MembersPanel workspace={selectedWorkspace} getToken={getToken} />
            </div>
          ) : (
            <p className="font-ui text-sm text-ink/60">Select or create a workspace to get started.</p>
          )}
        </main>
      </div>
    </div>
  );
}

function CreateTenantForm({ onCreate }: { onCreate: (name: string, slug: string) => void }) {
  const [name, setName] = useState("");

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="font-ui text-xl font-semibold text-ink">Set up your fund</h1>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const slug = name
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "");
          onCreate(name, slug || `fund-${Date.now()}`);
        }}
        className="flex flex-col gap-2"
      >
        <input
          required
          placeholder="Fund name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="rounded border border-ink/20 bg-paper px-3 py-2 font-ui text-sm"
        />
        <Button type="submit">Create fund</Button>
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
      <h3 className="font-ui text-sm font-medium text-ink">New workspace</h3>
      <input
        required
        placeholder="Codename (e.g. project-falcon)"
        value={codename}
        onChange={(event) => setCodename(event.target.value)}
        className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
      />
      <input
        placeholder="Real target name (optional)"
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

"use client";

import { useEffect, useState } from "react";

import { Button } from "@/design-system/components/button";

import { inviteMember, listMembers, listRoles, revokeMember, updateMemberRole } from "../api";
import type { Membership, Role, RoleInfo, Workspace } from "../types";
import { RoleBadge } from "./RoleBadge";

type GetToken = () => Promise<string | null>;

export function MembersPanel({ workspace, getToken }: { workspace: Workspace; getToken: GetToken }) {
  const [members, setMembers] = useState<Membership[]>([]);
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isOwner = workspace.my_role === "owner";

  async function refresh() {
    setMembers(await listMembers(getToken, workspace.id));
  }

  useEffect(() => {
    refresh();
    listRoles(getToken).then(setRoles);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace.id]);

  async function handleInvite(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const result = await inviteMember(getToken, workspace.id, { email, role });
      setInviteUrl(result.invite_url);
      setEmail("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to invite");
    }
  }

  async function handleRoleChange(membershipId: string, newRole: Role) {
    await updateMemberRole(getToken, workspace.id, membershipId, newRole);
    await refresh();
  }

  async function handleRevoke(membershipId: string) {
    await revokeMember(getToken, workspace.id, membershipId);
    await refresh();
  }

  return (
    <section className="flex flex-col gap-4">
      <h2 className="font-ui text-lg font-semibold text-ink">Members</h2>

      <ul className="flex flex-col gap-2">
        {members.map((member) => (
          <li
            key={member.id}
            className="flex items-center justify-between rounded-md border border-ink/10 px-3 py-2"
          >
            <div className="flex flex-col">
              <span className="font-ui text-sm text-ink">{member.invited_email}</span>
              <span className="font-ui text-xs text-ink/50">{member.status}</span>
            </div>
            <div className="flex items-center gap-2">
              {isOwner ? (
                <select
                  className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-xs capitalize"
                  value={member.role}
                  onChange={(event) => handleRoleChange(member.id, event.target.value as Role)}
                >
                  {roles.map((r) => (
                    <option key={r.role} value={r.role}>
                      {r.role}
                    </option>
                  ))}
                </select>
              ) : (
                <RoleBadge role={member.role} />
              )}
              {isOwner && member.status !== "revoked" ? (
                <Button variant="outline" size="dense" onClick={() => handleRevoke(member.id)}>
                  Revoke
                </Button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>

      {isOwner ? (
        <form onSubmit={handleInvite} className="flex flex-col gap-2 rounded-md border border-ink/10 p-3">
          <h3 className="font-ui text-sm font-medium text-ink">Invite a member</h3>
          <div className="flex gap-2">
            <input
              type="email"
              required
              placeholder="name@fund.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="flex-1 rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
            />
            <select
              value={role}
              onChange={(event) => setRole(event.target.value as Role)}
              className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm capitalize"
            >
              {roles.map((r) => (
                <option key={r.role} value={r.role}>
                  {r.role}
                </option>
              ))}
            </select>
            <Button type="submit">Invite</Button>
          </div>
          {role ? (
            <p className="font-ui text-xs text-ink/60">
              {roles.find((r) => r.role === role)?.description}
            </p>
          ) : null}
          {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}
          {inviteUrl ? (
            <p className="break-all font-ui text-xs text-ink/60">
              Invite link (dev only, no email sending yet): {inviteUrl}
            </p>
          ) : null}
        </form>
      ) : null}
    </section>
  );
}

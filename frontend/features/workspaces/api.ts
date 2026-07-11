import { apiFetch } from "@/lib/api";

import type {
  AuditEvent,
  Membership,
  MembershipInviteResult,
  Role,
  RoleInfo,
  Tenant,
  Workspace,
} from "./types";

type GetToken = () => Promise<string | null>;

export const listRoles = (getToken: GetToken) => apiFetch<RoleInfo[]>("/roles", { getToken });

export const createTenant = (getToken: GetToken, body: { name: string; slug: string }) =>
  apiFetch<Tenant>("/tenants", { method: "POST", body, getToken });

export const listWorkspaces = (getToken: GetToken, tenantId: string) =>
  apiFetch<Workspace[]>(`/tenants/${tenantId}/workspaces`, { getToken });

export const createWorkspace = (
  getToken: GetToken,
  tenantId: string,
  body: { codename: string; real_name?: string },
) => apiFetch<Workspace>(`/tenants/${tenantId}/workspaces`, { method: "POST", body, getToken });

export const getWorkspace = (getToken: GetToken, workspaceId: string) =>
  apiFetch<Workspace>(`/workspaces/${workspaceId}`, { getToken });

export const listMembers = (getToken: GetToken, workspaceId: string) =>
  apiFetch<Membership[]>(`/workspaces/${workspaceId}/members`, { getToken });

export const inviteMember = (
  getToken: GetToken,
  workspaceId: string,
  body: { email: string; role: Role },
) =>
  apiFetch<MembershipInviteResult>(`/workspaces/${workspaceId}/members`, {
    method: "POST",
    body,
    getToken,
  });

export const updateMemberRole = (
  getToken: GetToken,
  workspaceId: string,
  membershipId: string,
  role: Role,
) =>
  apiFetch<Membership>(`/workspaces/${workspaceId}/members/${membershipId}`, {
    method: "PATCH",
    body: { role },
    getToken,
  });

export const revokeMember = (getToken: GetToken, workspaceId: string, membershipId: string) =>
  apiFetch<void>(`/workspaces/${workspaceId}/members/${membershipId}`, {
    method: "DELETE",
    getToken,
  });

export const acceptInvite = (getToken: GetToken, token: string) =>
  apiFetch<Membership>("/invites/accept", { method: "POST", body: { token }, getToken });

export const listAuditEvents = (getToken: GetToken, workspaceId: string) =>
  apiFetch<AuditEvent[]>(`/workspaces/${workspaceId}/audit-events`, { getToken });

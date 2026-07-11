export type Role = "owner" | "analyst" | "approver" | "viewer";
export type MembershipStatus = "invited" | "active" | "revoked";

export interface RoleInfo {
  role: Role;
  description: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface Workspace {
  id: string;
  tenant_id: string;
  codename: string;
  real_name: string | null;
  created_at: string;
  my_role: Role | null;
}

export interface Membership {
  id: string;
  workspace_id: string;
  invited_email: string;
  role: Role;
  status: MembershipStatus;
  user_id: string | null;
}

export interface MembershipInviteResult {
  membership: Membership;
  invite_url: string;
}

export interface AuditEvent {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  actor_user_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

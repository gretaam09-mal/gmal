import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from db.models.enums import MembershipStatus, Role

ROLE_DESCRIPTIONS: dict[Role, str] = {
    Role.OWNER: "Full control: manage members, settings, and all workspace content.",
    Role.ANALYST: "Build and edit entity profiles, analyses, and memo drafts.",
    Role.APPROVER: "Review and approve memos before they go out, alongside analyst work.",
    Role.VIEWER: "Read-only access to the workspace's profiles, analyses, and memos.",
}


class RoleInfo(BaseModel):
    role: Role
    description: str


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceCreate(BaseModel):
    codename: str = Field(min_length=1, max_length=100)
    real_name: str | None = Field(default=None, max_length=200)


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    codename: str
    real_name: str | None
    created_at: datetime
    my_role: Role | None = None

    model_config = {"from_attributes": True}


class MembershipInvite(BaseModel):
    email: EmailStr
    role: Role


class MembershipOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    invited_email: str
    role: Role
    status: MembershipStatus
    user_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class MembershipInviteOut(BaseModel):
    membership: MembershipOut
    invite_url: str


class MembershipRoleUpdate(BaseModel):
    role: Role


class InviteAcceptRequest(BaseModel):
    token: str

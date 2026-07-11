import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from db.models.enums import MembershipStatus, ProfileFieldSource, Role
from engine.completeness.catalog import Section

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


class FieldCatalogEntryOut(BaseModel):
    key: str
    section: Section
    label: str
    weight: float
    used_for: str | None


class ProfileFieldIn(BaseModel):
    key: str
    value: Any = None
    source: ProfileFieldSource
    confirmed_at: datetime | None = None


class ProfileFieldOut(BaseModel):
    key: str
    value: Any
    source: ProfileFieldSource
    confirmed_at: datetime | None

    model_config = {"from_attributes": True}


class SectionCompletenessOut(BaseModel):
    section: Section
    score: float
    unknown_field_labels: tuple[str, ...]


class CompletenessOut(BaseModel):
    overall_score: float
    sections: tuple[SectionCompletenessOut, ...]
    unknown_field_labels: tuple[str, ...]


class EntityProfileOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    version: int
    is_current: bool
    companies_house_number: str | None
    created_at: datetime
    fields: list[ProfileFieldOut]
    completeness: CompletenessOut


class AutofillRequest(BaseModel):
    companies_house_number: str = Field(min_length=1, max_length=20)


class ProfileUpdateRequest(BaseModel):
    fields: list[ProfileFieldIn]

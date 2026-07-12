import uuid
from datetime import date, datetime
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


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    is_staff: bool

    model_config = {"from_attributes": True}


# --- F3: instrument-onboarding workbench (staff-only, /admin) --------------


class InstrumentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    jurisdiction: str = Field(default="UK", max_length=50)
    kind: str = Field(min_length=1, max_length=100)
    citation: str | None = Field(default=None, max_length=300)
    version_label: str = Field(min_length=1, max_length=100)
    source_url: str | None = None
    raw_text: str = Field(min_length=1)
    in_flight: bool = False


class ClauseOut(BaseModel):
    id: uuid.UUID
    clause_ref: str
    text: str
    ordinal: int

    model_config = {"from_attributes": True}


class InstrumentOut(BaseModel):
    id: uuid.UUID
    title: str
    jurisdiction: str
    kind: str
    citation: str | None
    in_flight: bool
    recorded_at: datetime

    model_config = {"from_attributes": True}


class InstrumentVersionOut(BaseModel):
    id: uuid.UUID
    instrument_id: uuid.UUID
    version_label: str
    source_url: str | None
    content_hash: str
    clauses: list[ClauseOut]


class InstrumentDetailOut(InstrumentOut):
    versions: list[InstrumentVersionOut]


class ExtractedFieldOut(BaseModel):
    value: str
    clause_ref: str
    confidence: int


class ObligationOut(BaseModel):
    id: uuid.UUID
    clause_id: uuid.UUID
    summary: str
    obligation_type: str
    fields: dict[str, ExtractedFieldOut]
    confidence: int
    extracted_by: str
    approved: bool
    approved_by_user_id: uuid.UUID | None
    approved_at: datetime | None

    model_config = {"from_attributes": True}


class ExtractObligationRequest(BaseModel):
    instrument_title: str = Field(min_length=1)


class ObligationUpdateRequest(BaseModel):
    summary: str | None = None
    obligation_type: str | None = None
    fields: dict[str, ExtractedFieldOut] | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)


class ObligationCorrectRequest(BaseModel):
    summary: str
    obligation_type: str
    fields: dict[str, ExtractedFieldOut]
    confidence: int = Field(ge=0, le=100)


class PredicateOut(BaseModel):
    id: uuid.UUID
    obligation_id: uuid.UUID
    predicate_key: str
    expression: dict[str, Any]
    status: str
    drafted_by_ai: bool
    approved_by_user_id: uuid.UUID | None
    approved_at: datetime | None

    model_config = {"from_attributes": True}


class PredicateCreateRequest(BaseModel):
    predicate_key: str = Field(min_length=1, max_length=100)
    expression: dict[str, Any]


class PredicateUpdateRequest(BaseModel):
    expression: dict[str, Any]


class PredicateTestResultOut(BaseModel):
    profile_name: str
    outcome: str
    missing_field_keys: tuple[str, ...]


class CostTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    drivers: list[dict[str, Any]] = Field(default_factory=list)
    formula: dict[str, Any]
    currency: str = Field(default="GBP", max_length=10)
    source_basis: str = Field(min_length=1, max_length=200)
    maturity_tier: str = Field(min_length=1, max_length=50)
    first_obligation_date: date | None = None
    transition_months: int = Field(default=0, ge=0)


class CostTemplateOut(BaseModel):
    id: uuid.UUID
    obligation_id: uuid.UUID | None
    name: str
    drivers: list[dict[str, Any]]
    formula: dict[str, Any]
    currency: str
    source_basis: str
    maturity_tier: str
    first_obligation_date: date | None
    transition_months: int
    valid_from: datetime
    valid_to: datetime | None

    model_config = {"from_attributes": True}


class OnboardingMetricOut(BaseModel):
    instrument_id: str
    instrument_title: str
    onboarding_hours: float
    started_at: str
    completed_at: str


# --- F4: applicability engine ------------------------------------------------


class AnalysisCreateRequest(BaseModel):
    entity_profile_id: uuid.UUID | None = None
    """Defaults to the workspace's current profile version if omitted."""
    discount_rate_pct: float = 0
    fx_rate: float = 1
    base_currency: str = Field(default="GBP", max_length=10)


class PhaseEntryOut(BaseModel):
    period: str
    amount: float


class AnalysisItemOut(BaseModel):
    id: uuid.UUID
    predicate_id: uuid.UUID
    instrument_title: str
    obligation_summary: str
    outcome: str
    missing_field_keys: tuple[str, ...]
    rationale: str
    clause_refs: tuple[str, ...]
    amount: float | None
    impact_low: float | None
    impact_high: float | None
    present_value: float | None
    phased_schedule: list[PhaseEntryOut]
    currency: str
    impact_band: str
    confidence: int
    first_obligation_date: str | None
    memo_status: str
    engine_version: str
    computed_at: datetime


class AnalysisOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    entity_profile_id: uuid.UUID
    status: str
    discount_rate_pct: float
    fx_rate: float
    base_currency: str
    created_at: datetime
    items: list[AnalysisItemOut]


class MemoCreateRequest(BaseModel):
    analysis_id: uuid.UUID
    title: str = Field(min_length=1, max_length=300)


class AssumptionOut(BaseModel):
    id: uuid.UUID
    key: str
    value: dict[str, Any]
    source: str
    note: str | None

    model_config = {"from_attributes": True}


class ReviewOut(BaseModel):
    id: uuid.UUID
    reviewer_user_id: uuid.UUID
    decision: str
    comment: str | None
    panel_firm: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoVersionOut(BaseModel):
    id: uuid.UUID
    memo_id: uuid.UUID
    version: int
    status: str
    content: dict[str, Any]
    confidence_grade: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    approved_by_user_id: uuid.UUID | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    assumptions: list[AssumptionOut]
    reviews: list[ReviewOut]
    inputs_changed: bool
    stale_reasons: list[str]


class MemoOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    analysis_id: uuid.UUID | None
    title: str
    created_by_user_id: uuid.UUID
    created_at: datetime
    used_in_ic: bool
    versions: list[MemoVersionOut]


class ReviewQueueEntryOut(BaseModel):
    memo_id: uuid.UUID
    memo_title: str
    version_id: uuid.UUID
    version_number: int
    status: str
    confidence_grade: str | None
    ambiguous_count: int
    submitted_at: datetime | None
    created_at: datetime


class ApproveMemoRequest(BaseModel):
    panel_firm: str | None = None


class UsedInIcRequest(BaseModel):
    used_in_ic: bool


class AssumptionOverrideRequest(BaseModel):
    value: dict[str, Any]
    note: str | None = None


class ChangeOut(BaseModel):
    field: str
    kind: str
    before: str | None
    after: str | None
    delta: str | None


class AssumptionOverrideResponse(BaseModel):
    version: MemoVersionOut
    change_note: str
    changes: list[ChangeOut]


class NewVersionRequest(BaseModel):
    change_note: str = Field(min_length=1, max_length=1000)

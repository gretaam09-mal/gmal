import enum


class Role(str, enum.Enum):
    """Workspace membership roles.

    One-liners shown to users when inviting a member (see
    frontend/features/workspaces for the UI copy — displayed as
    "assessment" there, see api/schemas.py::ROLE_DESCRIPTIONS):
      OWNER    — Full control: manage members, settings, and all assessment content.
      ANALYST  — Build and edit entity profiles, analyses, and memo drafts.
      APPROVER — Review and approve memos before they go out, alongside analyst work.
      VIEWER   — Read-only access to the assessment's profiles, analyses, and memos.
    """

    OWNER = "owner"
    ANALYST = "analyst"
    APPROVER = "approver"
    VIEWER = "viewer"


class MembershipStatus(str, enum.Enum):
    INVITED = "invited"
    ACTIVE = "active"
    REVOKED = "revoked"


class ProfileFieldSource(str, enum.Enum):
    REGISTRY = "registry"
    FILING = "filing"
    USER = "user"
    DEFAULT = "default"
    ESTIMATE = "estimate"
    UNKNOWN = "unknown"


class ReviewDecision(str, enum.Enum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class MemoStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class PredicateStatus(str, enum.Enum):
    """DRAFT predicates (hand-written or P-PREDICATE-ASSIST output) are
    never evaluated by F4 — only APPROVED ones are. See
    docs/CONVENTIONS.md rule 2: once APPROVED, a predicate is immutable
    (enforced by a DB trigger — see the instrument_onboarding migration)."""

    DRAFT = "draft"
    APPROVED = "approved"


class AnalysisItemOutcome(str, enum.Enum):
    """Tri-state result of evaluating one predicate against a profile.

    AMBIGUOUS means the profile is missing a fact the predicate needs —
    see AnalysisItem.missing_field_keys for which one(s)."""

    BINDS = "binds"
    DOES_NOT_BIND = "does_not_bind"
    AMBIGUOUS = "ambiguous"


class SourceDocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class SweepRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"

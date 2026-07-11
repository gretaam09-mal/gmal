import enum


class Role(str, enum.Enum):
    """Workspace membership roles.

    One-liners shown to users when inviting a member (see
    frontend/features/workspaces for the UI copy):
      OWNER    — Full control: manage members, settings, and all workspace content.
      ANALYST  — Build and edit entity profiles, analyses, and memo drafts.
      APPROVER — Review and approve memos before they go out, alongside analyst work.
      VIEWER   — Read-only access to the workspace's profiles, analyses, and memos.
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

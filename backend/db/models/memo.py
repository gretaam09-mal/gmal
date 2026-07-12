import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, CreatedAtMixin, PrimaryKeyMixin, TenantScopedMixin, TimestampMixin
from db.models.enums import MemoStatus, ReviewDecision


class Memo(Base, PrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """The mutable pointer to a memo's version history.

    Only `title` and which version is current ever change here; the
    content itself lives in immutable MemoVersion rows.
    """

    __tablename__ = "memos"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    versions: Mapped[list["MemoVersion"]] = relationship(back_populates="memo")


class MemoVersion(Base, PrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin):
    """A snapshot of a memo's content, mutable only while DRAFT/IN_REVIEW.

    CONVENTIONS.md rule #2: once `status` is APPROVED, the row is locked —
    a DB trigger (see migration) rejects any further UPDATE/DELETE. Before
    approval, `content`/`status` may be edited in place by the override
    workflow (services/memo.py) so a Draft can be recomputed without
    minting a new version each time; approving is the one transition that
    seals it, and any change after that creates a new MemoVersion with a
    change note (see services/memo.py, P-DIFF-NOTE).
    """

    __tablename__ = "memo_versions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    memo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memos.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[MemoStatus] = mapped_column(
        Enum(MemoStatus, name="memo_status"), nullable=False, default=MemoStatus.DRAFT
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    confidence_grade: Mapped[str | None] = mapped_column(String(1), nullable=True)
    """A-D, from engine/confidence's published rubric (profile
    completeness, template maturity, extraction confidence, scenario-source
    quality) — computed, never chosen by the composition prompt."""

    memo: Mapped["Memo"] = relationship(back_populates="versions")


class Assumption(Base, PrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin):
    """A named assumption pinned to a specific memo version.

    Every default/estimate/override/probability shown in the memo's
    assumption register is one of these — `source` names where it came
    from (e.g. "cost_template:<id>", "scenario_base_rate:<key>",
    "analyst_override:<user_id>", "profile_field:<key>") so the register
    can label each entry's provenance per F6's requirements.
    """

    __tablename__ = "assumptions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    memo_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memo_versions.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="unknown")
    note: Mapped[str | None] = mapped_column(String, nullable=True)


class Review(Base, PrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin):
    """A reviewer's decision on a memo version."""

    __tablename__ = "reviews"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    memo_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memo_versions.id"), nullable=False, index=True
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    decision: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision, name="review_decision"), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(String, nullable=True)

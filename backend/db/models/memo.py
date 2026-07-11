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
    """An immutable snapshot of a memo's content.

    CONVENTIONS.md rule #2: once created, never updated — a DB trigger
    (see migration) rejects UPDATE/DELETE as a backstop. Approving a memo
    updates `status`/`approved_*` via a narrow allowed transition, not by
    editing content; see services/composition for the approval flow once
    it exists.
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

    memo: Mapped["Memo"] = relationship(back_populates="versions")


class Assumption(Base, PrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin):
    """A named assumption pinned to a specific memo version."""

    __tablename__ = "assumptions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    memo_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memo_versions.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
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

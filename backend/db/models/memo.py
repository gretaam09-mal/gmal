import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
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
    used_in_ic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """F10 board metric: whether this memo was actually used in an IC
    pack — a plain Analyst-settable tag on the mutable pointer row, not
    on any (immutable) version, since "was this used" is a fact about the
    memo as a whole, not one specific version's content."""

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
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """When this version moved Draft -> In Review — see
    services/memo.py::submit_for_review. Paired with approved_at to derive
    F7's automatic review-minutes board metric; never set directly by a
    reviewer, only by that transition."""

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
    panel_firm: Mapped[str | None] = mapped_column(String, nullable=True)
    """The external panel firm the reviewer sits on, where the review was
    performed by outside counsel rather than in-house — F7 requires this
    on the approved document when set. Free-text label, same shape as
    Assumption.source/CostTemplate.source_basis elsewhere in this schema."""


class ReviewCorrection(Base, PrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin):
    """A reviewer's fix, made while reviewing a memo, that was persisted
    back to the shared instrument/template layer as a new version — not
    just patched into this one memo. Append-only: it is a record of what
    happened, not something later editable.

    Exactly one of obligation_id/cost_template_id is set, pointing at the
    *new* (post-correction) row — services/instrument_onboarding.py's
    correct_obligation/attach_cost_template already do the actual
    versioning; this table only records that a review triggered it, so
    F8's lineage appendix can show "this figure changed because reviewer
    X corrected obligation Y during this review".
    """

    __tablename__ = "review_corrections"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    memo_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memo_versions.id"), nullable=False, index=True
    )
    obligation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligations.id"), nullable=True
    )
    cost_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_templates.id"), nullable=True
    )
    corrected_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    note: Mapped[str] = mapped_column(String, nullable=False)


class MemoInputChangeFlag(Base, PrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin):
    """F9: a signal that one of a memo version's regulatory inputs
    changed after the memo was produced — never a mutation of the memo
    version itself (which may already be APPROVED and immutable), just an
    append-only side record the memo's GET response joins against to show
    an "inputs changed" banner and name the specific instrument version
    that moved.
    """

    __tablename__ = "memo_input_change_flags"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    memo_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memo_versions.id"), nullable=False, index=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    instrument_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instrument_versions.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(String, nullable=False)

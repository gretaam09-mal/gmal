import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, CreatedAtMixin, PrimaryKeyMixin, TenantScopedMixin, TimestampMixin
from db.models.enums import MembershipStatus, Role


class Tenant(Base, PrimaryKeyMixin, TimestampMixin):
    """A fund. The top of the tenancy tree — everything else hangs off it."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="tenant")


class User(Base, PrimaryKeyMixin, TimestampMixin):
    """A person. Not tenant-scoped — a user can hold memberships across tenants."""

    __tablename__ = "users"

    clerk_user_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_staff: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    """Gates the F3 instrument-onboarding workbench (/admin, staff-only —
    see api/deps.py::require_staff). Nobody is staff by default; grant it
    with backend/scripts/grant_staff.py. Unrelated to workspace Role,
    which governs tenant data, not this internal reference-data tooling."""


class Workspace(Base, PrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    """A deal workspace within a tenant (fund).

    `codename` is always set (defaults to a generated codename) so a real
    target name is never required; `real_name` is optional and may be
    filled in once a target is confirmed.
    """

    __tablename__ = "workspaces"

    codename: Mapped[str] = mapped_column(String, nullable=False)
    real_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="workspaces")
    memberships: Mapped[list["Membership"]] = relationship(back_populates="workspace")

    __table_args__ = (
        UniqueConstraint("tenant_id", "codename", name="uq_workspace_tenant_codename"),
    )


class Membership(Base, PrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    """A user's (or pending invitee's) role within a single workspace.

    `user_id` is null for an invitation that hasn't been accepted yet;
    `invited_email` is always set so the invite flow has somewhere to send
    the invite regardless of acceptance state.
    """

    __tablename__ = "memberships"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    invited_email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), nullable=False)
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, name="membership_status"),
        nullable=False,
        default=MembershipStatus.INVITED,
    )
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="memberships")
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("workspace_id", "invited_email", name="uq_membership_workspace_invitee"),
    )


class AuditEvent(Base, PrimaryKeyMixin, CreatedAtMixin):
    """Append-only record of every state change.

    CONVENTIONS.md rule #2: nothing here is ever updated or deleted by
    application code; a DB trigger (see migration) rejects UPDATE/DELETE
    as a backstop. workspace_id is nullable because some events are
    tenant-level (e.g. tenant created) rather than tied to one workspace;
    tenant_id is nullable too, for the handful of events that predate any
    tenant (F10: a user's first sign-in, before they've joined or created
    one) — those rows fall outside every tenant-scoped RLS policy (see
    the row_level_security migration), same as MetricsEvent/
    ErrorRegisterEntry's platform-level rows.
    """

    __tablename__ = "audit_events"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (Index("ix_audit_events_entity", "entity_type", "entity_id"),)

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, BitemporalMixin, PrimaryKeyMixin, TenantScopedMixin
from db.models.enums import ProfileFieldSource


class EntityProfile(Base, PrimaryKeyMixin, TenantScopedMixin, BitemporalMixin):
    """An immutable, versioned snapshot of a workspace's target entity profile.

    Every save creates a new version rather than editing one in place
    (CONVENTIONS.md rule #2). `is_current` marks the latest version for a
    workspace and is the only column ever flipped after insert (from True
    to False on the prior version, in the same transaction that inserts
    the next one) — a narrow, deliberate exception to immutability that
    exists purely to make "give me the current profile" a cheap lookup.
    """

    __tablename__ = "entity_profiles"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    companies_house_number: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    fields: Mapped[list["ProfileField"]] = relationship(back_populates="entity_profile")

    __table_args__ = (
        UniqueConstraint("workspace_id", "version", name="uq_entity_profile_workspace_version"),
    )


class ProfileField(Base, PrimaryKeyMixin, TenantScopedMixin, BitemporalMixin):
    """A single field on one profile version.

    `field_key` is a dotted path (e.g. "footprint.has_overseas_ops") into
    the section catalog defined in engine/completeness/catalog.py.
    `field_value` is null when the source is UNKNOWN — unknown is always a
    valid, explicit answer, never a blocking validation error.
    """

    __tablename__ = "profile_fields"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    entity_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity_profiles.id"), nullable=False, index=True
    )
    field_key: Mapped[str] = mapped_column(String, nullable=False)
    field_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[ProfileFieldSource] = mapped_column(
        Enum(ProfileFieldSource, name="profile_field_source"), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    entity_profile: Mapped["EntityProfile"] = relationship(back_populates="fields")

    __table_args__ = (
        UniqueConstraint("entity_profile_id", "field_key", name="uq_profile_field_version_key"),
    )

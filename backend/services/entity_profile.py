import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import EntityProfile, ProfileField, ProfileFieldSource
from services.companies_house.snapshot import EntitySnapshot


@dataclass(frozen=True)
class FieldUpdate:
    value: Any
    source: ProfileFieldSource
    confirmed_at: datetime | None = None


def get_current_profile(session: Session, workspace_id: uuid.UUID) -> EntityProfile | None:
    return session.execute(
        select(EntityProfile).where(
            EntityProfile.workspace_id == workspace_id, EntityProfile.is_current.is_(True)
        )
    ).scalar_one_or_none()


def get_profile_fields(session: Session, entity_profile_id: uuid.UUID) -> list[ProfileField]:
    return list(
        session.execute(
            select(ProfileField).where(ProfileField.entity_profile_id == entity_profile_id)
        ).scalars()
    )


def create_profile_version(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    field_updates: dict[str, FieldUpdate],
    companies_house_number: str | None = None,
) -> EntityProfile:
    """Create a new, immutable profile version, carrying forward any field
    not present in field_updates from the current version.

    CONVENTIONS.md rule #2: this never edits a prior version's fields —
    it only ever inserts. Flipping the old version's is_current to False
    is the one narrow exception the immutability trigger allows.
    """
    now = datetime.now(UTC)
    current = get_current_profile(session, workspace_id)

    carried: dict[str, tuple[Any, ProfileFieldSource, datetime | None]] = {}
    if current is not None:
        for field in get_profile_fields(session, current.id):
            carried[field.field_key] = (field.field_value, field.source, field.confirmed_at)
        current.is_current = False

    for key, update in field_updates.items():
        carried[key] = (update.value, update.source, update.confirmed_at)

    new_profile = EntityProfile(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        version=(current.version + 1) if current else 1,
        is_current=True,
        companies_house_number=(
            companies_house_number
            if companies_house_number is not None
            else (current.companies_house_number if current else None)
        ),
        created_by_user_id=created_by_user_id,
        valid_from=now,
    )
    session.add(new_profile)
    session.flush()

    for key, (value, source, confirmed_at) in carried.items():
        session.add(
            ProfileField(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                entity_profile_id=new_profile.id,
                field_key=key,
                field_value=value,
                source=source,
                confirmed_at=confirmed_at,
                valid_from=now,
            )
        )

    return new_profile


def field_updates_from_snapshot(snapshot: EntitySnapshot) -> dict[str, FieldUpdate]:
    """Companies House data becomes REGISTRY/FILING-sourced field updates —
    confirmed_at is left unset (nobody's confirmed it yet, the register
    just says so) until a human confirms it in the guided editor."""
    officers = [
        {
            "name": officer.name,
            "role": officer.role,
            "appointed_on": officer.appointed_on,
            "resigned_on": officer.resigned_on,
        }
        for officer in snapshot.officers
    ]
    registry = ProfileFieldSource.REGISTRY
    return {
        "identity.company_name": FieldUpdate(snapshot.company_name, registry),
        "identity.company_number": FieldUpdate(snapshot.company_number, registry),
        "identity.company_status": FieldUpdate(snapshot.company_status, registry),
        "identity.incorporated_on": FieldUpdate(snapshot.incorporated_on, registry),
        "identity.officers": FieldUpdate(officers, registry),
        "scale.band": FieldUpdate(snapshot.scale_band, ProfileFieldSource.FILING),
        "activity.sic_codes": FieldUpdate(snapshot.sic_codes, registry),
    }

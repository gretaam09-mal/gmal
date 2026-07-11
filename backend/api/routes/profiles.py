from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_companies_house_client, get_current_user, get_workspace_db, require_role
from api.schemas import (
    AutofillRequest,
    CompletenessOut,
    EntityProfileOut,
    FieldCatalogEntryOut,
    ProfileFieldOut,
    ProfileUpdateRequest,
    SectionCompletenessOut,
)
from db.models import EntityProfile, Membership, ProfileField, Role, User
from engine.completeness.calculator import FieldState, compute_completeness
from engine.completeness.catalog import FIELD_CATALOG
from services.audit import record_audit_event
from services.companies_house import (
    CompaniesHouseClient,
    CompanyNotFoundError,
    fetch_entity_snapshot,
)
from services.companies_house.client import CompaniesHouseError
from services.entity_profile import (
    FieldUpdate,
    create_profile_version,
    field_updates_from_snapshot,
    get_current_profile,
    get_profile_fields,
)

router = APIRouter(tags=["entity-profile"])

_ANY_ROLE = (Role.OWNER, Role.ANALYST, Role.APPROVER, Role.VIEWER)


@router.get("/profile-field-catalog", response_model=list[FieldCatalogEntryOut])
async def get_field_catalog(
    _current_user: User = Depends(get_current_user),
) -> list[FieldCatalogEntryOut]:
    """Single source of truth for the guided editor's sections, labels,
    and footprint-flag "used for" hints — see frontend/features/profile."""
    return [
        FieldCatalogEntryOut(
            key=f.key, section=f.section, label=f.label, weight=f.weight, used_for=f.used_for
        )
        for f in FIELD_CATALOG
    ]


def _to_out(profile: EntityProfile, fields: list[ProfileField]) -> EntityProfileOut:
    field_states = {f.field_key: FieldState(f.field_key, f.source.value) for f in fields}
    completeness = compute_completeness(field_states)
    return EntityProfileOut(
        id=profile.id,
        workspace_id=profile.workspace_id,
        version=profile.version,
        is_current=profile.is_current,
        companies_house_number=profile.companies_house_number,
        created_at=profile.recorded_at,
        fields=[
            ProfileFieldOut(
                key=f.field_key, value=f.field_value, source=f.source, confirmed_at=f.confirmed_at
            )
            for f in fields
        ],
        completeness=CompletenessOut(
            overall_score=completeness.overall_score,
            sections=tuple(
                SectionCompletenessOut(
                    section=s.section, score=s.score, unknown_field_labels=s.unknown_field_labels
                )
                for s in completeness.sections
            ),
            unknown_field_labels=completeness.unknown_field_labels,
        ),
    )


@router.get("/workspaces/{workspace_id}/profile", response_model=EntityProfileOut | None)
async def get_profile(
    membership: Membership = Depends(require_role(*_ANY_ROLE)),
    session: Session = Depends(get_workspace_db),
):
    profile = get_current_profile(session, membership.workspace_id)
    if profile is None:
        return None
    return _to_out(profile, get_profile_fields(session, profile.id))


@router.get("/workspaces/{workspace_id}/profile/versions", response_model=list[EntityProfileOut])
async def list_profile_versions(
    membership: Membership = Depends(require_role(*_ANY_ROLE)),
    session: Session = Depends(get_workspace_db),
):
    profiles = session.execute(
        select(EntityProfile)
        .where(EntityProfile.workspace_id == membership.workspace_id)
        .order_by(EntityProfile.version.desc())
    ).scalars()
    return [_to_out(p, get_profile_fields(session, p.id)) for p in profiles]


@router.post("/workspaces/{workspace_id}/profile/autofill", response_model=EntityProfileOut)
async def autofill_profile(
    body: AutofillRequest,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(Role.OWNER, Role.ANALYST)),
    session: Session = Depends(get_workspace_db),
    ch_client: CompaniesHouseClient = Depends(get_companies_house_client),
):
    try:
        snapshot = fetch_entity_snapshot(ch_client, body.companies_house_number)
    except CompanyNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except CompaniesHouseError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    profile = create_profile_version(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        created_by_user_id=current_user.id,
        field_updates=field_updates_from_snapshot(snapshot),
        companies_house_number=snapshot.company_number,
    )
    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="profile.autofilled",
        entity_type="entity_profile",
        entity_id=profile.id,
        payload={"companies_house_number": snapshot.company_number, "version": profile.version},
    )
    session.commit()
    return _to_out(profile, get_profile_fields(session, profile.id))


@router.put("/workspaces/{workspace_id}/profile", response_model=EntityProfileOut)
async def update_profile(
    body: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(require_role(Role.OWNER, Role.ANALYST)),
    session: Session = Depends(get_workspace_db),
):
    field_updates = {
        f.key: FieldUpdate(value=f.value, source=f.source, confirmed_at=f.confirmed_at)
        for f in body.fields
    }
    profile = create_profile_version(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        created_by_user_id=current_user.id,
        field_updates=field_updates,
    )
    record_audit_event(
        session,
        tenant_id=membership.tenant_id,
        workspace_id=membership.workspace_id,
        actor_user_id=current_user.id,
        action="profile.updated",
        entity_type="entity_profile",
        entity_id=profile.id,
        payload={"version": profile.version, "updated_fields": list(field_updates.keys())},
    )
    session.commit()
    return _to_out(profile, get_profile_fields(session, profile.id))

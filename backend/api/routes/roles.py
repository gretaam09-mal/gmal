from fastapi import APIRouter, Depends

from api.deps import get_current_user
from api.schemas import ROLE_DESCRIPTIONS, RoleInfo
from db.models import User

router = APIRouter(tags=["roles"])


@router.get("/roles", response_model=list[RoleInfo])
async def list_roles(_current_user: User = Depends(get_current_user)) -> list[RoleInfo]:
    """One-liners for the invite-member UI — single source of truth."""
    return [RoleInfo(role=role, description=text) for role, text in ROLE_DESCRIPTIONS.items()]

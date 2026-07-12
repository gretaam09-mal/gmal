from fastapi import APIRouter, Depends

from api.deps import get_current_user
from api.schemas import MeOut
from db.models import User

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Lets the frontend know its own identity and whether to show the
    /admin workbench nav — /admin is never linked for non-staff, but the
    admin layout still checks this to redirect a non-staff visitor away
    rather than showing a 403 page."""
    return current_user

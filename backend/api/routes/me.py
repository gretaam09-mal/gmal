from fastapi import APIRouter, Depends

from api.config import get_settings
from api.deps import get_current_user
from api.schemas import MeOut
from db.models import User

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
async def get_me(current_user: User = Depends(get_current_user)) -> MeOut:
    """Lets the frontend know its own identity and whether to show the
    /admin workbench nav — /admin is never linked for non-staff, but the
    admin layout still checks this to redirect a non-staff visitor away
    rather than showing a 403 page.

    Also self-diagnoses PROVISION_ADMIN_EMAILS elevation (see
    api/deps.py::_maybe_elevate_to_staff) — is_staff already reflects
    whatever that dependency decided a moment ago on this same request,
    so admin_emails_configured/email_matches_admin_list here explain why,
    without needing database or environment access to figure out."""
    admin_emails = get_settings().admin_emails_list
    return MeOut(
        id=current_user.id,
        email=current_user.email,
        is_staff=current_user.is_staff,
        admin_emails_configured=bool(admin_emails),
        email_matches_admin_list=current_user.email.lower() in admin_emails,
    )

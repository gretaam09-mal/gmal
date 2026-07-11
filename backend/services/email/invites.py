import logging

logger = logging.getLogger("provision.email")


def send_invite_email(*, to: str, workspace_codename: str, invite_url: str) -> None:
    """Stub: logs instead of sending. Real delivery is a later phase.

    The API returns the invite link directly in the response for now
    (see api/routes/workspaces.py) so invites are usable in local dev and
    tests without real email infrastructure.
    """
    logger.info(
        "invite email (stub): to=%s workspace=%s url=%s", to, workspace_codename, invite_url
    )

"""Maps a Companies House accounts filing category to a coarse scale band.

Not arithmetic (CONVENTIONS.md rule #1 governs engine/, not this) — this is
a fixed lookup translating one external vocabulary (accounts type) into
Provision's own, for entity-profile auto-fill. No number is computed here;
`engine/impact` is where a scale band eventually feeds a cost estimate.
"""

_ACCOUNTS_TYPE_TO_SCALE_BAND = {
    "micro-entity": "micro",
    "small": "small",
    "total-exemption-small": "small",
    "total-exemption-full": "small",
    "unaudited-abridged": "small",
    "abridged": "small",
    "medium": "medium",
    "full": "large",
    "group": "large",
    "dormant": "dormant",
}


def scale_band_from_accounts_type(accounts_type: str | None) -> str:
    if accounts_type is None:
        return "unknown"
    return _ACCOUNTS_TYPE_TO_SCALE_BAND.get(accounts_type, "unknown")

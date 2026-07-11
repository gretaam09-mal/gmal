"""Companies House public data API client.

Fetches identity, officers, SIC codes, and filing-derived scale fields for
Entity Profile auto-fill (see api/routes/profiles.py). Every call is
fixture-tested (data/fixtures/companies_house/*.json via httpx.MockTransport)
— no test in this repo makes a live request to Companies House.
"""

from services.companies_house.client import (
    CompaniesHouseClient,
    CompaniesHouseError,
    CompanyNotFoundError,
)
from services.companies_house.snapshot import EntitySnapshot, fetch_entity_snapshot

__all__ = [
    "CompaniesHouseClient",
    "CompaniesHouseError",
    "CompanyNotFoundError",
    "EntitySnapshot",
    "fetch_entity_snapshot",
]

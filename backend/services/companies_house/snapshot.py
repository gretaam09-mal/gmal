from dataclasses import dataclass

from services.companies_house.client import CompaniesHouseClient, Officer, RegisteredAddress
from services.companies_house.scale import scale_band_from_accounts_type


@dataclass(frozen=True)
class EntitySnapshot:
    """Everything Entity Profile auto-fill needs from Companies House, in
    one shot — see api/routes/profiles.py."""

    company_name: str
    company_number: str
    company_status: str
    company_type: str
    incorporated_on: str | None
    sic_codes: list[str]
    registered_office_address: RegisteredAddress | None
    officers: list[Officer]
    scale_band: str
    last_accounts_made_up_to: str | None


def fetch_entity_snapshot(client: CompaniesHouseClient, company_number: str) -> EntitySnapshot:
    profile = client.get_company_profile(company_number)
    officers = client.get_officers(company_number)
    return EntitySnapshot(
        company_name=profile.company_name,
        company_number=profile.company_number,
        company_status=profile.company_status,
        company_type=profile.company_type,
        incorporated_on=profile.date_of_creation,
        sic_codes=profile.sic_codes,
        registered_office_address=profile.registered_office_address,
        officers=officers,
        scale_band=scale_band_from_accounts_type(profile.last_accounts_type),
        last_accounts_made_up_to=profile.last_accounts_made_up_to,
    )

import httpx
from pydantic import BaseModel

from api.config import get_settings


class CompaniesHouseError(Exception):
    """Raised for any non-404 error from the Companies House API."""


class CompanyNotFoundError(CompaniesHouseError):
    """Raised when a company number doesn't exist on the register."""

    def __init__(self, company_number: str) -> None:
        self.company_number = company_number
        super().__init__(f"No company found for number {company_number!r}")


class RegisteredAddress(BaseModel):
    address_line_1: str | None = None
    address_line_2: str | None = None
    locality: str | None = None
    postal_code: str | None = None
    country: str | None = None


class CompanyProfile(BaseModel):
    company_name: str
    company_number: str
    company_status: str
    company_type: str
    jurisdiction: str | None = None
    date_of_creation: str | None = None
    sic_codes: list[str] = []
    registered_office_address: RegisteredAddress | None = None
    last_accounts_type: str | None = None
    last_accounts_made_up_to: str | None = None


class Officer(BaseModel):
    name: str
    role: str
    appointed_on: str | None = None
    resigned_on: str | None = None
    nationality: str | None = None
    occupation: str | None = None

    @property
    def is_active(self) -> bool:
        return self.resigned_on is None


class CompaniesHouseClient:
    """Thin wrapper over the public Companies House REST API.

    Auth is HTTP Basic with the API key as username and an empty password
    (Companies House's convention, not ours). `transport` is injectable so
    tests can point this at a fixture-backed httpx.MockTransport instead
    of the network — see tests/unit/test_companies_house_client.py.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.companies_house_api_key
        self._client = httpx.Client(
            base_url=base_url or settings.companies_house_base_url,
            auth=(key, "") if key else None,
            transport=transport,
            timeout=10.0,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CompaniesHouseClient":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def get_company_profile(self, company_number: str) -> CompanyProfile:
        response = self._client.get(f"/company/{company_number}")
        if response.status_code == 404:
            raise CompanyNotFoundError(company_number)
        if response.status_code >= 400:
            raise CompaniesHouseError(f"Companies House returned {response.status_code}")

        data = response.json()
        last_accounts = data.get("accounts", {}).get("last_accounts", {})
        address = data.get("registered_office_address")
        return CompanyProfile(
            company_name=data["company_name"],
            company_number=data["company_number"],
            company_status=data["company_status"],
            company_type=data.get("type", "unknown"),
            jurisdiction=data.get("jurisdiction"),
            date_of_creation=data.get("date_of_creation"),
            sic_codes=data.get("sic_codes", []),
            registered_office_address=RegisteredAddress(**address) if address else None,
            last_accounts_type=last_accounts.get("type"),
            last_accounts_made_up_to=last_accounts.get("made_up_to"),
        )

    def get_officers(self, company_number: str) -> list[Officer]:
        response = self._client.get(f"/company/{company_number}/officers")
        if response.status_code == 404:
            raise CompanyNotFoundError(company_number)
        if response.status_code >= 400:
            raise CompaniesHouseError(f"Companies House returned {response.status_code}")

        data = response.json()
        return [
            Officer(
                name=item["name"],
                role=item.get("officer_role", "unknown"),
                appointed_on=item.get("appointed_on"),
                resigned_on=item.get("resigned_on"),
                nationality=item.get("nationality"),
                occupation=item.get("occupation"),
            )
            for item in data.get("items", [])
        ]

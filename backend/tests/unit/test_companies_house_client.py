import json
from pathlib import Path

import httpx
import pytest

from services.companies_house.client import (
    CompaniesHouseClient,
    CompaniesHouseError,
    CompanyNotFoundError,
)
from services.companies_house.scale import scale_band_from_accounts_type
from services.companies_house.snapshot import fetch_entity_snapshot

FIXTURES = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "companies_house"

_PROFILES = {
    "12345678": json.loads((FIXTURES / "company_profile_active.json").read_text()),
    "87654321": json.loads((FIXTURES / "company_profile_dormant_micro.json").read_text()),
}
_OFFICERS = {
    "12345678": json.loads((FIXTURES / "officers_active.json").read_text()),
    "87654321": json.loads((FIXTURES / "officers_empty.json").read_text()),
}


def _fixture_handler(request: httpx.Request) -> httpx.Response:
    parts = request.url.path.strip("/").split("/")
    # ["company", "{number}"] or ["company", "{number}", "officers"]
    company_number = parts[1]
    if len(parts) == 2:
        profile = _PROFILES.get(company_number)
        if profile is None:
            return httpx.Response(404, json={"errors": [{"error": "not-found"}]})
        return httpx.Response(200, json=profile)
    if len(parts) == 3 and parts[2] == "officers":
        officers = _OFFICERS.get(company_number)
        if officers is None:
            return httpx.Response(404, json={"errors": [{"error": "not-found"}]})
        return httpx.Response(200, json=officers)
    return httpx.Response(404)


@pytest.fixture
def client():
    transport = httpx.MockTransport(_fixture_handler)
    with CompaniesHouseClient(api_key="test-key", transport=transport) as c:
        yield c


def test_get_company_profile_maps_fields(client):
    profile = client.get_company_profile("12345678")

    assert profile.company_name == "EXAMPLE TARGET LIMITED"
    assert profile.company_status == "active"
    assert profile.sic_codes == ["62012", "62020"]
    assert profile.registered_office_address.postal_code == "EC1A 1AA"
    assert profile.last_accounts_type == "small"


def test_get_company_profile_not_found_raises(client):
    with pytest.raises(CompanyNotFoundError):
        client.get_company_profile("00000000")


def test_get_officers_includes_resigned_with_flag(client):
    officers = client.get_officers("12345678")

    assert len(officers) == 3
    active = [o for o in officers if o.is_active]
    assert {o.name for o in active} == {"SMITH, John Robert", "DOE, Jane"}
    resigned = next(o for o in officers if not o.is_active)
    assert resigned.name == "PREVIOUS, Peter"
    assert resigned.resigned_on == "2019-11-30"


def test_scale_band_from_accounts_type():
    assert scale_band_from_accounts_type("micro-entity") == "micro"
    assert scale_band_from_accounts_type("small") == "small"
    assert scale_band_from_accounts_type("full") == "large"
    assert scale_band_from_accounts_type(None) == "unknown"
    assert scale_band_from_accounts_type("something-new-companies-house-invents") == "unknown"


def test_fetch_entity_snapshot_combines_profile_and_officers(client):
    snapshot = fetch_entity_snapshot(client, "12345678")

    assert snapshot.company_name == "EXAMPLE TARGET LIMITED"
    assert snapshot.scale_band == "small"
    assert len(snapshot.officers) == 3
    assert snapshot.sic_codes == ["62012", "62020"]


def test_fetch_entity_snapshot_dormant_micro_company(client):
    snapshot = fetch_entity_snapshot(client, "87654321")

    assert snapshot.company_name == "SMALL HOLDCO LIMITED"
    assert snapshot.scale_band == "micro"
    assert snapshot.officers == []


def test_server_error_raises_companies_house_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with CompaniesHouseClient(api_key="test-key", transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(CompaniesHouseError):
            c.get_company_profile("12345678")

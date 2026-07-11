# Companies House API setup

Entity Profile auto-fill (identity, officers, SIC codes, filing-derived
scale) uses the free, public
[Companies House API](https://developer.company-information.service.gov.uk/).
All tests run against local fixtures (`data/fixtures/companies_house/`), so
no key is needed for CI or local development of the client itself — only
for actually calling the live API.

## What to create

1. Register for a free account at
   [developer.company-information.service.gov.uk](https://developer.company-information.service.gov.uk/).
2. Create an application, then create a **REST API key** for it (live
   environment — the "test" environment only returns synthetic test
   companies, which is fine for manual poking but not required for this
   repo's automated tests).

## Where the key goes

Backend (`backend/.env`, not committed):

```
PROVISION_COMPANIES_HOUSE_API_KEY=your-key-here
```

No other configuration is needed — `services/companies_house/client.py`
sends it as the HTTP Basic Auth username (Companies House's convention)
against `https://api.company-information.service.gov.uk`.

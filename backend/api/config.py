from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, sourced from environment variables."""

    model_config = SettingsConfigDict(env_prefix="PROVISION_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+psycopg://provision:provision@localhost:5432/provision"
    aws_region: str = "eu-west-2"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        """Managed Postgres providers (Render, Heroku, ...) hand out a plain
        postgres:// or postgresql:// URL; SQLAlchemy needs the driver named
        explicitly. Rewriting it here means every deployment can just set
        the provider's raw connection string with no manual editing."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    # Clerk (see docs/adr/0001-clerk-for-authentication.md). Unset in dev/CI
    # until a Clerk application exists — see docs/runbooks/clerk-setup.md.
    clerk_jwks_url: str | None = None
    clerk_issuer: str | None = None

    # Signs workspace-invite links (services/invites.py). Dev-only default —
    # every real deployment must override this.
    app_secret_key: str = "dev-only-insecure-secret-key-change-me"

    # Companies House public data API — see docs/runbooks/companies-house-setup.md.
    companies_house_api_key: str | None = None
    companies_house_base_url: str = "https://api.company-information.service.gov.uk"

    # P-EXTRACT / P-PREDICATE-ASSIST (services/extraction, services/predicate_assist)
    # — see ai/prompts/. Unset in dev/CI/tests, which always inject a
    # fixture-backed provider instead (see services/extraction/fixture_provider.py)
    # rather than needing a real key to run the suite.
    anthropic_api_key: str | None = None
    anthropic_extraction_model: str = "claude-sonnet-5"

    # Comma-separated origins allowed to call the API from a browser (the
    # frontend is on a different host in every deployment). "*" in dev.
    cors_allowed_origins: str = "*"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    # Comma-separated emails auto-granted staff (admin workbench) access on
    # their next sign-in — see api/deps.py::_maybe_elevate_to_staff and
    # docs/runbooks/anthropic-setup.md. Blank by default: nobody is staff
    # from this mechanism until an operator sets it.
    admin_emails: str = ""

    @property
    def admin_emails_list(self) -> list[str]:
        return [email.strip().lower() for email in self.admin_emails.split(",") if email.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

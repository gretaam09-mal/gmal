from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, sourced from environment variables."""

    model_config = SettingsConfigDict(env_prefix="PROVISION_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+psycopg://provision:provision@localhost:5432/provision"
    aws_region: str = "eu-west-2"

    # Clerk (see docs/adr/0001-clerk-for-authentication.md). Unset in dev/CI
    # until a Clerk application exists — see docs/runbooks/clerk-setup.md.
    clerk_jwks_url: str | None = None
    clerk_issuer: str | None = None

    # Signs workspace-invite links (services/invites.py). Dev-only default —
    # every real deployment must override this.
    app_secret_key: str = "dev-only-insecure-secret-key-change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()

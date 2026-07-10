from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, sourced from environment variables."""

    model_config = SettingsConfigDict(env_prefix="PROVISION_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+psycopg://provision:provision@localhost:5432/provision"
    aws_region: str = "eu-west-2"


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Application settings loaded from environment variables (CONNECTIVITY_ prefix)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONNECTIVITY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = Field(default=8001, ge=1, le=65535)

    bq_adapter: Literal["mock", "bigquery"] = "mock"
    bq_project: str = ""
    bq_dataset: str = ""
    bq_dataset_uk: str = ""
    bq_dataset_eu: str = ""

    llm_adapter: Literal["mock"] = "mock"

    cors_origins: str = ""
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    rate_limit_enabled: bool = False

    # API-key auth — load from environment / Secret Manager, never hardcode values
    api_key_enabled: bool = True
    api_key: SecretStr = Field(default=SecretStr(""))
    # Tenant scope bound to the key; populated from env / Secret Manager
    api_key_country: str = ""
    api_key_operator: str = ""
    api_key_brand: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

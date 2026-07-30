"""Application settings loaded from environment variables (CONNECTIVITY_ prefix)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
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

    llm_adapter: Literal["mock"] = "mock"

    cors_origins: str = ""
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    rate_limit_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

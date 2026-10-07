"""Validated, environment-based configuration."""

import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MLPP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    mongodb_uri: SecretStr = SecretStr("mongodb://127.0.0.1:27017/?directConnection=true")
    mongodb_database: str = Field(
        default="ml_pipeline_pro", min_length=1, max_length=63, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    dependency_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    artifact_root: Path = Path("artifacts")
    dataset_root: Path = Path("examples/data")
    dataset_max_bytes: int = Field(default=10_000_000, ge=1, le=100_000_000)
    dataset_max_rows: int = Field(default=100_000, ge=3, le=1_000_000)
    project_api_keys: dict[str, SecretStr] = Field(default_factory=dict)
    worker_lease_seconds: int = Field(default=30, ge=10, le=300)
    worker_max_attempts: int = Field(default=3, ge=1, le=10)

    @field_validator("project_api_keys")
    @classmethod
    def validate_project_keys(cls, value: dict[str, SecretStr]) -> dict[str, SecretStr]:
        if any(
            not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", project) or len(key.get_secret_value()) < 16
            for project, key in value.items()
        ):
            raise ValueError(
                "Project IDs must be valid and API keys must have at least 16 characters"
            )
        return value

    @model_validator(mode="after")
    def production_requires_project_keys(self):
        if self.environment == "production" and not self.project_api_keys:
            raise ValueError("Production requires project API keys")
        return self

    @field_validator("mongodb_uri", "redis_url")
    @classmethod
    def validate_connection_url(cls, value: SecretStr, info: ValidationInfo) -> SecretStr:
        allowed = (
            {"mongodb", "mongodb+srv"} if info.field_name == "mongodb_uri" else {"redis", "rediss"}
        )
        try:
            parsed = urlsplit(value.get_secret_value())
            if parsed.scheme not in allowed or not parsed.hostname or parsed.fragment:
                raise ValueError("Invalid connection URL")
        except ValueError:
            raise ValueError("Connection URL must have a supported scheme and hostname") from None
        return value

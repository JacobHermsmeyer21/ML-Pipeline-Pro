"""Validated, environment-based configuration."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationInfo, field_validator
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
    mongodb_uri: SecretStr = SecretStr("mongodb://127.0.0.1:27017")
    mongodb_database: str = Field(
        default="ml_pipeline_pro", min_length=1, max_length=63, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    dependency_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    artifact_root: Path = Path("artifacts")

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

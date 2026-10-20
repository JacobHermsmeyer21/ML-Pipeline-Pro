"""Validated, environment-based configuration."""

import ipaddress
import re
from pathlib import Path
from typing import Any, Literal
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
    dataset_upload_enabled: bool = False
    dataset_max_bytes: int = Field(default=10_000_000, ge=1, le=100_000_000)
    dataset_max_rows: int = Field(default=100_000, ge=3, le=1_000_000)
    project_api_keys: dict[str, SecretStr] = Field(default_factory=dict)
    worker_lease_seconds: int = Field(default=30, ge=10, le=300)
    worker_max_attempts: int = Field(default=3, ge=1, le=10)
    chat_enabled: bool = False
    chat_backend: Literal["openai", "ollama"] = "openai"
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    chat_protocol: Literal["native", "guided"] = "native"
    chat_tokenizer_path: Path | None = None
    chat_model: str | None = Field(default=None, min_length=1, max_length=128)
    chat_model_origin: str = "http://127.0.0.1:11434"
    chat_api_origin: str = "http://127.0.0.1:8000"
    chat_unbounded_diagnostic: bool = False
    chat_timeout_seconds: float | None = Field(default=60, gt=0, le=300, allow_inf_nan=False)
    chat_model_timeout_seconds: float | None = Field(default=20, gt=0, le=300, allow_inf_nan=False)
    chat_action_timeout_seconds: float = Field(default=30, gt=0, le=60, allow_inf_nan=False)
    chat_max_model_calls: int = Field(default=5, strict=True, ge=1, le=10)
    chat_max_tool_calls: int = Field(default=4, strict=True, ge=1, le=8)
    chat_max_output_tokens: int = Field(default=1024, strict=True, ge=128, le=4096)
    chat_context_tokens: int = Field(default=8192, strict=True, ge=1024, le=16384)

    @field_validator("chat_timeout_seconds", "chat_model_timeout_seconds", mode="before")
    @classmethod
    def diagnostic_null_timeout(cls, value):
        return None if isinstance(value, str) and value.strip().lower() == "none" else value

    @field_validator("chat_tokenizer_path", mode="before")
    @classmethod
    def blank_tokenizer_path(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator(
        "chat_max_model_calls",
        "chat_max_tool_calls",
        "chat_max_output_tokens",
        "chat_context_tokens",
        mode="before",
    )
    @classmethod
    def chat_integer_setting(cls, value: Any) -> Any:
        # Environment/dotenv values are strings; retain strict rejection of
        # booleans and fractional numbers after parsing decimal integer settings.
        if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
            return int(value)
        return value

    @field_validator("chat_model")
    @classmethod
    def model_identifier(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("chat_backend") == "openai":
            if value is not None and not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", value):
                raise ValueError("OpenAI model must be an explicit model identifier")
        elif value is not None and (
            not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_./-]*:[a-zA-Z0-9_][a-zA-Z0-9_.-]*", value)
            or "cloud" in value.lower()
        ):
            raise ValueError("Chat model must be an explicit local model tag")
        return value

    @field_validator("chat_model_origin")
    @classmethod
    def private_model_origin(cls, value: str) -> str:
        try:
            parsed = urlsplit(value)
            host = parsed.hostname or ""
            local = host in {"localhost", "ollama", "host.docker.internal"}
            try:
                address = ipaddress.ip_address(host)
                local = address.is_loopback or any(
                    address in ipaddress.ip_network(network)
                    for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
                )
            except ValueError:
                local = local or bool(
                    re.fullmatch(
                        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\."
                        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.svc\.cluster\.local",
                        host,
                    )
                )
            if not local:
                raise ValueError
        except ValueError:
            raise ValueError("Model origin must use an explicit local/private host") from None
        return cls._http_origin(value)

    @field_validator("chat_api_origin")
    @classmethod
    def api_origin(cls, value: str) -> str:
        # The existing tool transport accepts operator-configured HTTP(S) origins.
        return cls._http_origin(value)

    @staticmethod
    def _http_origin(value: str) -> str:
        try:
            parsed = urlsplit(value)
            if (
                not (
                    parsed.scheme in {"http", "https"}
                    and parsed.hostname
                    and parsed.username is None
                    and parsed.password is None
                    and parsed.path in {"", "/"}
                    and not parsed.query
                    and not parsed.fragment
                )
                or parsed.port == 0
            ):
                raise ValueError
        except ValueError:
            raise ValueError(
                "Chat origin must be HTTP(S) without credentials, path, query or fragment"
            ) from None
        return value

    @model_validator(mode="after")
    def chat_limits(self):
        if self.chat_backend == "openai" and (
            self.chat_protocol != "native"
            or self.chat_tokenizer_path is not None
            or self.chat_unbounded_diagnostic
        ):
            raise ValueError(
                "OpenAI requires native protocol, no local tokenizer and finite limits"
            )
        null_timeouts = (
            self.chat_model_timeout_seconds is None and self.chat_timeout_seconds is None
        )
        if self.chat_unbounded_diagnostic:
            if self.environment == "production" or not null_timeouts:
                raise ValueError(
                    "Unbounded diagnostics require non-production and two null timeouts"
                )
        elif self.chat_model_timeout_seconds is None or self.chat_timeout_seconds is None:
            raise ValueError("Null chat timeouts require the explicit unbounded diagnostic flag")
        if not null_timeouts and self.chat_model_timeout_seconds > self.chat_timeout_seconds:
            raise ValueError("Model timeout cannot exceed the overall chat timeout")
        if self.chat_max_output_tokens >= self.chat_context_tokens:
            raise ValueError("Chat context must leave space for input tokens")
        # Missing model configuration must leave the direct API able to start.
        return self

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

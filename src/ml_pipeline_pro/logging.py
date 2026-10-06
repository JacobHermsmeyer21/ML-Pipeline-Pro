"""JSON logs with connection credential redaction."""

import json
import logging
import re
from datetime import UTC, datetime
from urllib.parse import unquote, urlsplit

from ml_pipeline_pro.config import Settings

_URI_CREDENTIALS = re.compile(r"((?:mongodb(?:\+srv)?|rediss?|https?)://)[^\s/]+@", re.I)
_BEARER_TOKEN = re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/-]+=*", re.I)
_SECRET_VALUE = re.compile(r"((?:password|api[_-]?key|access[_-]?token)\s*[=:]\s*)[^\s,;]+", re.I)


class JsonFormatter(logging.Formatter):
    def __init__(self, secrets: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.secrets = tuple(sorted((s for s in secrets if s), key=len, reverse=True))

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("correlation_id", "method", "path", "status_code", "duration_ms"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Redact before JSON encoding so quotes and escapes in passwords remain safe.
        return json.dumps({key: self.redact(value) for key, value in payload.items()})

    def redact(self, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = _URI_CREDENTIALS.sub(r"\1[REDACTED]@", value)
        value = _BEARER_TOKEN.sub(r"\1[REDACTED]", value)
        value = _SECRET_VALUE.sub(r"\1[REDACTED]", value)
        for secret in self.secrets:
            value = value.replace(secret, "[REDACTED]")
        return value


def configure_logging(settings: Settings) -> None:
    secrets = [key.get_secret_value() for key in settings.project_api_keys.values()]
    for connection_url in (settings.mongodb_uri, settings.redis_url):
        password = urlsplit(connection_url.get_secret_value()).password
        if password:
            secrets.extend((password, unquote(password)))

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(tuple(secrets)))
    for name in ("ml_pipeline_pro", "pymongo", "redis", "uvicorn"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.setLevel(settings.log_level)
        logger.propagate = False
    for name in ("uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True

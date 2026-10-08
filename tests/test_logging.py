import json
import logging

import pytest

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.logging import JsonFormatter, configure_logging


def test_logs_are_json_and_preserve_request_context():
    record = logging.LogRecord("example", logging.INFO, __file__, 1, "Completed", (), None)
    record.correlation_id = "request-42"
    record.status_code = 200

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "Completed"
    assert payload["correlation_id"] == "request-42"
    assert payload["status_code"] == 200
    assert payload["timestamp"].endswith("+00:00")


def test_log_credentials_are_redacted_from_messages_and_tracebacks():
    try:
        raise RuntimeError("redis://user:database-secret@localhost:6379")
    except RuntimeError as exc:
        record = logging.LogRecord(
            "example",
            logging.ERROR,
            __file__,
            1,
            "mongodb://user:database-secret@localhost Bearer auth-token api_key=key-secret %s",
            ('quote"secret',),
            (type(exc), exc, exc.__traceback__),
        )

    encoded = JsonFormatter(('quote"secret',)).format(record)
    payload = json.loads(encoded)

    for secret in ("database-secret", "auth-token", "key-secret", 'quote"secret'):
        assert secret not in encoded
        assert secret not in payload["message"]
    assert "[REDACTED]" in payload["exception"]


@pytest.mark.parametrize(
    "name",
    [
        "langchain",
        "langchain_core",
        "langchain_ollama",
        "langsmith",
        "ollama",
        "httpx",
        "httpcore",
    ],
)
def test_model_and_http_client_loggers_use_configured_secret_redaction(name):
    names = (
        "ml_pipeline_pro",
        "pymongo",
        "redis",
        "uvicorn",
        "celery",
        "kombu",
        "langchain",
        "langchain_core",
        "langchain_ollama",
        "langsmith",
        "ollama",
        "httpx",
        "httpcore",
        "uvicorn.error",
        "uvicorn.access",
    )
    originals = {
        item: (
            logging.getLogger(item).handlers[:],
            logging.getLogger(item).level,
            logging.getLogger(item).propagate,
        )
        for item in names
    }
    logger = logging.getLogger(name)
    try:
        configure_logging(Settings(_env_file=None, project_api_keys={"demo": "fixture-known-key"}))
        record = logging.LogRecord(name, logging.ERROR, __file__, 1, "fixture-known-key", (), None)
        assert logger.propagate is False
        assert "fixture-known-key" not in logger.handlers[0].formatter.format(record)
    finally:
        for item, original in originals.items():
            restored = logging.getLogger(item)
            restored.handlers, restored.level, restored.propagate = original

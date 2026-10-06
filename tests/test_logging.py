import json
import logging

from ml_pipeline_pro.logging import JsonFormatter


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

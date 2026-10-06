import pytest
from pydantic import ValidationError

from ml_pipeline_pro.config import Settings


def test_config_reads_environment_and_hides_connection_secrets(monkeypatch):
    monkeypatch.setenv("MLPP_MONGODB_URI", "mongodb://user:private-password@localhost:27017")
    monkeypatch.setenv("MLPP_MONGODB_DATABASE", "example_project")
    monkeypatch.setenv("MLPP_LOG_LEVEL", "WARNING")

    settings = Settings(_env_file=None)

    assert settings.mongodb_database == "example_project"
    assert settings.log_level == "WARNING"
    assert "private-password" not in repr(settings)
    assert "private-password" not in settings.model_dump_json()


@pytest.mark.parametrize("timeout", [0, -1, 31, float("inf"), float("nan")])
def test_invalid_dependency_timeouts_are_rejected(timeout):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, dependency_timeout_seconds=timeout)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mongodb_uri", "http://user:private-password@localhost"),
        ("mongodb_uri", "mongodb://"),
        ("redis_url", "file:///private-password"),
        ("redis_url", "redis://localhost#fragment"),
        ("mongodb_database", "invalid.database"),
        ("log_level", "INVALID"),
    ],
)
def test_invalid_configuration_fails_without_printing_the_input(field, value):
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **{field: value})

    assert "private-password" not in str(exc_info.value)


def test_dotenv_configuration_is_supported(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MLPP_MONGODB_DATABASE=from_dotenv\n", encoding="utf-8")

    assert Settings(_env_file=env_file).mongodb_database == "from_dotenv"

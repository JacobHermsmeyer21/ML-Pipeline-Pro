import pytest
from pydantic import ValidationError

from ml_pipeline_pro.config import Settings


def test_chat_defaults_and_missing_model_leave_direct_api_configuration_available():
    settings = Settings(_env_file=None)
    assert settings.chat_enabled is False
    assert settings.chat_model is None
    assert settings.chat_backend == "ollama"
    assert Settings(_env_file=None, chat_enabled=True).chat_model is None


def test_chat_integer_limits_read_dotenv_and_environment(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("MLPP_CHAT_MAX_MODEL_CALLS=3\nMLPP_CHAT_CONTEXT_TOKENS=4096\n")
    monkeypatch.setenv("MLPP_CHAT_MAX_OUTPUT_TOKENS", "512")
    settings = Settings(_env_file=path)
    assert settings.chat_max_model_calls == 3
    assert settings.chat_context_tokens == 4096
    assert settings.chat_max_output_tokens == 512


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://[::1]:11434",
        "http://10.2.3.4:11434",
        "http://172.16.1.1",
        "http://192.168.1.1",
        "http://[fd00::1]:11434",
        "http://ollama:11434",
        "http://host.docker.internal:11434",
        "http://ollama.models.svc.cluster.local:11434",
    ],
)
def test_local_model_origin_accepts_loopback_and_explicit_private_deployment_hosts(origin):
    assert Settings(_env_file=None, chat_model_origin=origin).chat_model_origin == origin


@pytest.mark.parametrize(
    "origin",
    [
        "https://ollama.com",
        "http://8.8.8.8",
        "http://203.0.113.1",
        "http://0.0.0.0",
        "http://169.254.169.254",
        "http://[fe80::1]",
        "http://[ff02::1]",
        "http://evil.svc.cluster.local",
        "http://user:private-password@localhost",
        "http://localhost/api",
        "http://localhost?token=private-password",
        "http://localhost#fragment",
        "http://localhost:99999",
        "http://localhost:0",
        "file://localhost",
        "http://[",
    ],
)
def test_model_origin_rejects_external_special_hosts_and_non_origin_urls(origin):
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, chat_model_origin=origin)
    assert "private-password" not in str(caught.value)


def test_trusted_api_origin_preserves_existing_transport_host_policy():
    assert (
        Settings(_env_file=None, chat_api_origin="https://api.example.org").chat_api_origin
        == "https://api.example.org"
    )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chat_api_origin="https://api.example.org/api/v1")


@pytest.mark.parametrize(
    "tag",
    [
        "model",
        "model:",
        ":tag",
        "model:cloud",
        "model:tag?key=secret",
        "model name:tag",
        "../model:tag",
    ],
)
def test_local_model_requires_explicit_tag_and_rejects_cloud_tags(tag):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chat_model=tag)


@pytest.mark.parametrize("tag", ["model:1b", "library/model:q4_K_M", "model.name:latest"])
def test_local_model_accepts_explicit_artifact_tags(tag):
    assert Settings(_env_file=None, chat_model=tag).chat_model == tag


@pytest.mark.parametrize(
    "config",
    [
        {"chat_model_timeout_seconds": 31, "chat_timeout_seconds": 30},
        {"chat_max_output_tokens": 1024, "chat_context_tokens": 1024},
        {"chat_timeout_seconds": float("nan")},
        {"chat_timeout_seconds": float("inf")},
        {"chat_model_timeout_seconds": 0},
        {"chat_action_timeout_seconds": 61},
        {"chat_max_model_calls": 11},
        {"chat_max_tool_calls": 0},
        {"chat_context_tokens": 16385},
        {"chat_max_output_tokens": 127},
        {"chat_max_model_calls": True},
        {"chat_max_tool_calls": 1.5},
        {"chat_context_tokens": "8192.0"},
    ],
)
def test_chat_resource_limits_reject_invalid_or_incompatible_budgets(config):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **config)

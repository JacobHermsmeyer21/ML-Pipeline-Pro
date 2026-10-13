from fastapi.testclient import TestClient

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.main import create_app, create_model_app, create_tuning_app


def test_domain_services_preserve_existing_operations_and_exclude_other_owners():
    settings = Settings(_env_file=None, environment="test")
    combined_spec = create_app(settings).openapi()
    model_spec = create_model_app(settings).openapi()
    tuning_spec = create_tuning_app(settings).openapi()
    combined = combined_spec["paths"]
    models = model_spec["paths"]
    tuning = tuning_spec["paths"]
    health = {"/api/v1/health/live", "/api/v1/health/ready"}
    assert set(models) | set(tuning) == set(combined)
    assert set(models) & set(tuning) == health
    assert "/api/v1/chat" in models and "/api/v1/experiments" in models
    assert "/api/v1/tuning-jobs" in tuning
    assert all(path.startswith("/api/v1/tuning-jobs") for path in set(tuning) - health)
    for path, operations in {**models, **tuning}.items():
        assert operations == combined[path]
    for spec in (model_spec, tuning_spec):
        for name, schema in spec["components"]["schemas"].items():
            assert schema == combined_spec["components"]["schemas"][name]


def test_tuning_lifecycle_does_not_open_chat_clients_even_when_chat_is_enabled(fake_connections):
    settings = Settings(
        _env_file=None,
        environment="test",
        chat_enabled=True,
        project_api_keys={"demo": "demo-secret-for-tests"},
    )
    with TestClient(create_tuning_app(settings)) as client:
        assert client.app.state.conversation_model is None
        assert client.app.state.conversation_transport is None
        response = client.get("/api/v1/health/ready", headers={"X-Correlation-ID": "tuning"})
        assert response.status_code == 200
        assert response.json()["correlation_id"] == "tuning"
        assert client.get("/api/v1/chat").status_code == 404
        denied = client.get(
            "/api/v1/tuning-jobs",
            headers={"X-Correlation-ID": "denied", "X-Project-ID": "demo", "X-API-Key": "wrong"},
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["correlation_id"] == "denied"
        assert client.get("/tuning/docs").status_code == 200
    assert fake_connections.closed

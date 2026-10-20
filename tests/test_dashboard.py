import io
from pathlib import Path

from fastapi.testclient import TestClient

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.main import create_model_app, create_monitoring_app, create_tuning_app


def test_dashboard_assets_are_local_and_have_a_bounded_content_policy(client):
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert "Pipeline agent" in response.text
    policy = response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in policy and "frame-src http://127.0.0.1:3000" in policy
    assert "unsafe-inline" not in policy and "frame-ancestors 'self'" in policy
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-cache"
    for asset in ("app.js", "styles.css", "example.csv", "reply-errors.js"):
        assert client.get("/dashboard/" + asset).status_code == 200
    assert client.get("/dashboard", follow_redirects=False).headers["location"] == "/dashboard/"
    assert client.get("/dashboard/missing.js").status_code == 404


def test_config_only_exposes_public_capabilities_and_upload_effective_limits(app, client):
    app.state.settings.dataset_max_bytes = 20_000_000
    app.state.settings.project_api_keys = {"demo": "a-secret-that-must-not-appear"}
    response = client.get("/dashboard/config.json")
    assert response.status_code == 200
    assert response.json() == {
        "uploads_enabled": False,
        "max_upload_bytes": 10_000_000,
        "max_dataset_rows": 100_000,
        "grafana_origin": "http://127.0.0.1:3000",
        "chat_enabled": False,
        "chat_model": None,
    }
    assert "secret" not in response.text and "mongodb" not in response.text
    app.state.settings.dataset_max_bytes = 100
    assert client.get("/dashboard/config.json").json()["max_upload_bytes"] == 100


def test_dashboard_is_owned_by_model_service_only():
    settings = Settings(_env_file=None, environment="test")
    assert TestClient(create_model_app(settings)).get("/dashboard/").status_code == 200
    for factory in (create_tuning_app, create_monitoring_app):
        assert TestClient(factory(settings)).get("/dashboard/").status_code == 404


def test_packaged_example_is_the_validated_workflow_fixture():
    source = Path("examples/data/classification.csv").read_bytes()
    packaged = Path("src/ml_pipeline_pro/dashboard/example.csv").read_bytes()
    # Keep the user-downloadable input identical to the supported demo fixture.
    assert packaged == source
    assert len(io.StringIO(packaged.decode()).readlines()) == 121

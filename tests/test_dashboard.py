import base64
import hashlib
import io
import json
import re
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
    assert client.get("/dashboard/example.csv").status_code == 200
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
        "chat_backend": "ollama",
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


def test_dashboard_references_only_served_local_assets(client):
    html = client.get("/dashboard/").text
    refs = re.findall(r'(?:src|href)="(/dashboard/[^"#]+)"', html)
    assert any(ref.endswith(".js") for ref in refs) and any(ref.endswith(".css") for ref in refs)
    for ref in refs:
        assert client.get(ref).status_code == 200, ref
    # Inline style attributes would need 'unsafe-hashes'; the policy forbids them.
    assert "style=" not in html


def test_dashboard_has_no_unhashed_inline_code():
    root = Path("src/ml_pipeline_pro/dashboard")
    html = (root / "index.html").read_text()
    hashes = json.loads((root / "csp-hashes.json").read_text())
    for tag, directive in (("script", "script-src"), ("style", "style-src")):
        for body in re.findall(rf"<{tag}(?![^>]*\bsrc=)[^>]*>(.*?)</{tag}>", html, re.S):
            digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
            assert f"'sha256-{digest}'" in hashes[directive]


def test_csp_header_includes_build_hashes(client):
    hashes = json.loads(Path("src/ml_pipeline_pro/dashboard/csp-hashes.json").read_text())
    # React islands make Astro emit inline loader code, which must be allowed only by hash.
    assert hashes["script-src"] and hashes["style-src"]
    policy = client.get("/dashboard/").headers["Content-Security-Policy"]
    directives = dict(part.strip().split(" ", 1) for part in policy.split(";") if part.strip())
    for directive in ("script-src", "style-src"):
        assert directives[directive].startswith("'self'")
        for digest in hashes[directive]:
            assert digest in directives[directive].split()
    assert "unsafe-" not in policy

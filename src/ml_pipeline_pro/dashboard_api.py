"""Packaged local workspace; API credentials remain in the browser's memory."""

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ml_pipeline_pro.dataset_files import UPLOAD_MAX_BYTES


def load_csp_hashes(directory: Path) -> dict[str, list[str]]:
    """Read build-time hashes of the inline code Astro emits; absent means none allowed."""
    try:
        saved = json.loads((directory / "csp-hashes.json").read_text())
    except FileNotFoundError:
        saved = {}
    return {name: list(saved.get(name, [])) for name in ("script-src", "style-src")}


class DashboardFiles(StaticFiles):
    def __init__(self, *, directory: Path, html: bool = False):
        super().__init__(directory=directory, html=html)
        hashes = load_csp_hashes(directory)
        script = " ".join(["'self'", *hashes["script-src"]])
        style = " ".join(["'self'", *hashes["style-src"]])
        self.policy = (
            f"default-src 'self'; script-src {script}; style-src {style}; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "frame-src http://127.0.0.1:3000; object-src 'none'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'self'"
        )

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Content-Security-Policy"] = self.policy
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-cache"
        return response


def install_dashboard(app: FastAPI) -> None:
    @app.get("/dashboard", include_in_schema=False)
    async def dashboard_redirect():
        return RedirectResponse("/dashboard/", status_code=307)

    @app.get("/dashboard/config.json", include_in_schema=False)
    async def dashboard_config(request: Request):
        settings = request.app.state.settings
        return {
            "uploads_enabled": settings.dataset_upload_enabled,
            "max_upload_bytes": min(settings.dataset_max_bytes, UPLOAD_MAX_BYTES),
            "max_dataset_rows": settings.dataset_max_rows,
            "grafana_origin": "http://127.0.0.1:3000",
            "chat_enabled": settings.chat_enabled,
            "chat_backend": settings.chat_backend,
            "chat_model": settings.chat_model,
        }

    app.mount(
        "/dashboard", DashboardFiles(directory=Path(__file__).with_name("dashboard"), html=True)
    )

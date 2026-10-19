"""Packaged local workspace; API credentials remain in the browser's memory."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ml_pipeline_pro.dataset_files import UPLOAD_MAX_BYTES


class DashboardFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "frame-src http://127.0.0.1:3000; object-src 'none'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'self'"
        )
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
            "chat_model": settings.chat_model,
        }

    app.mount(
        "/dashboard", DashboardFiles(directory=Path(__file__).with_name("dashboard"), html=True)
    )

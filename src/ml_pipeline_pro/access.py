"""Project selection and optional project API keys for local development."""

import secrets
from typing import Annotated

from fastapi import Header, Request

from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.schemas import ProjectId


def project_access(
    request: Request,
    project_id: Annotated[ProjectId, Header(alias="X-Project-ID")],
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str:
    configured = request.app.state.settings.project_api_keys
    if configured:
        expected = configured.get(project_id)
        matches = secrets.compare_digest(
            (api_key or "").encode(),
            (expected.get_secret_value() if expected else "").encode(),
        )
        if expected is None or api_key is None or not matches:
            raise ApiError(403, "project_access_denied", "Access to this project is denied")
    return project_id

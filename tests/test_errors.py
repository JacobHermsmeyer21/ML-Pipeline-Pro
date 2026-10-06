from fastapi import HTTPException
from pydantic import BaseModel


def test_missing_routes_have_a_consistent_error(client):
    response = client.get("/api/v1/unknown", headers={"X-Correlation-ID": "missing-route"})

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "correlation_id": "missing-route",
        }
    }


def test_http_errors_preserve_required_headers(client):
    response = client.post("/api/v1/health/live")

    assert response.status_code == 405
    assert "GET" in response.headers["Allow"]
    assert response.json()["error"]["code"] == "method_not_allowed"


class ExampleRequest(BaseModel):
    count: int


def test_validation_errors_do_not_echo_user_input(app, client):
    @app.post("/test/validation")
    async def validate(body: ExampleRequest):
        return body

    response = client.post("/test/validation", json={"count": "private-user-input"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"]["fields"][0]["location"] == "body.count"
    assert "private-user-input" not in response.text


def test_unexpected_errors_hide_exception_details_and_keep_request_ids(app, client):
    @app.get("/test/crash")
    async def crash():
        raise RuntimeError("internal-secret")

    response = client.get("/test/crash", headers={"X-Correlation-ID": "crash-request"})

    assert response.status_code == 500
    assert response.headers["X-Correlation-ID"] == "crash-request"
    assert response.json()["error"]["correlation_id"] == "crash-request"
    assert response.json()["error"]["code"] == "internal_error"
    assert "internal-secret" not in response.text


def test_explicit_http_exception(app, client):
    @app.get("/test/unauthorized")
    async def unauthorized():
        raise HTTPException(status_code=401, detail="Authentication required")

    response = client.get("/test/unauthorized")

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Authentication required"

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_api import get_conversation_store
from ml_pipeline_pro.conversation_qwen_counter import QwenConversationModel
from ml_pipeline_pro.conversation_schemas import ConversationHistory, ConversationTurn
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.main import create_app
from tests.test_conversation_actions import fixture


def test_safe_validation_details_survive_http_history_and_offline_replay(fake_connections):
    from ml_pipeline_pro.conversation_diagnostics import ReplyValidationError
    from tests.conversation_memory import MemoryConversations
    from tests.test_conversation_service import ScriptedModel

    model = ScriptedModel(ReplyValidationError("reply_schema", "invalid_reply_schema"))
    app = create_app(
        Settings(_env_file=None, chat_enabled=True), chat_model_factory=lambda _: model
    )
    store = MemoryConversations()
    app.dependency_overrides[get_conversation_store] = lambda: store
    body = {"request_id": "first", "expected_revision": 0, "message": "inspect"}
    headers = {"X-Project-ID": "demo", "X-Correlation-ID": "saved-rejection"}
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", headers=headers, json=body)
        assert response.status_code == 200  # Persisted turn failure, not a transport error.
        first = response.json()
        assert first["status"] == "failed" and first["error"]["http_status"] == 422
        assert first["error"]["details"] == {
            "validation_stage": "reply_schema",
            "validation_reason": "invalid_reply_schema",
        }
        assert first["correlation_id"] == "saved-rejection"
        path = "/api/v1/conversations/" + first["conversation_id"]
        assert client.get(path, headers=headers).json()["turns"][0] == first
        assert client.post("/api/v1/chat", headers=headers, json=body).json() == first
        assert len(model.messages) == 1
        assert client.get(path, headers={"X-Project-ID": "foreign"}).status_code == 404
        # Historical generic errors keep their original public representation.
        legacy = ConversationTurn.model_validate(first)
        legacy.error.pop("details")
        assert "details" not in ConversationTurn.model_validate(legacy.model_dump()).error


def test_explicit_tokenizer_factory_stays_offline_and_closes(fake_connections, tmp_path):
    app = create_app(
        Settings(
            chat_backend="ollama",
            _env_file=None,
            chat_enabled=True,
            chat_model="mlpp-qwen2.5:7b-instruct-q4_K_M-json-tools-v1",
            chat_tokenizer_path=tmp_path / "absent-tokenizer.json",
        )
    )
    with TestClient(app):
        model = app.state.conversation_model
        assert isinstance(model, QwenConversationModel)
        assert model._native is None and model._counter is None
    assert model._closed is True
    assert (
        Settings(chat_backend="ollama", _env_file=None, chat_tokenizer_path="").chat_tokenizer_path
        is None
    )


def test_disabled_chat_and_decisions_preserve_authenticated_audit_reads(app):
    settings, action = fixture()
    store = AsyncMock()
    store.action.return_value = action
    store.history.return_value = ConversationHistory(
        conversation_id="conversation", revision=1, turns=[], limit=50, offset=0
    )
    app.dependency_overrides[get_conversation_store] = lambda: store
    with TestClient(app) as client:
        headers = {"X-Project-ID": "demo", "X-Correlation-ID": "current"}
        response = client.post(
            "/api/v1/chat",
            headers=headers,
            json={"request_id": "first", "message": "hello", "expected_revision": 0},
        )
        assert (
            response.status_code == 503 and response.json()["error"]["code"] == "chat_unavailable"
        )
        response = client.post(
            "/api/v1/conversations/conversation/actions/action/decision",
            headers=headers,
            json={"decision": "approve", "arguments_hash": "a" * 64},
        )
        assert response.status_code == 503
        assert client.get("/api/v1/conversations/conversation", headers=headers).status_code == 200
        response = client.get("/api/v1/conversations/conversation/actions/action", headers=headers)
        assert response.status_code == 200 and "submission_key" not in response.text
        assert response.headers["X-Correlation-ID"] == "current"


def test_valid_project_keys_reach_scoped_not_found_and_invalid_keys_reject(app):
    from pydantic import SecretStr

    app.state.settings.project_api_keys = {
        "demo": SecretStr("demo-secret"),
        "foreign": SecretStr("foreign-secret"),
    }
    store = AsyncMock()
    store.history.side_effect = ApiError(404, "conversation_not_found", "Not found")
    app.dependency_overrides[get_conversation_store] = lambda: store
    with TestClient(app) as client:
        path = "/api/v1/conversations/conversation"
        assert (
            client.get(path, headers={"X-Project-ID": "foreign", "X-API-Key": "wrong"}).status_code
            == 403
        )
        store.history.assert_not_called()
        response = client.get(
            path, headers={"X-Project-ID": "foreign", "X-API-Key": "foreign-secret"}
        )
        assert response.status_code == 404
        store.history.assert_awaited_once_with("foreign", "conversation", limit=50, offset=0)


def test_request_cap_counts_streamed_utf8_before_body_parsing(app):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat",
            headers={"X-Project-ID": "demo", "X-Correlation-ID": "cap"},
            content=iter([b'{"message":"', b"x" * 65536, b'"}']),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "chat_limit_exceeded"
        assert response.headers["X-Correlation-ID"] == "cap"


def test_enabled_chat_replay_returns_original_execution_correlation_and_closes_model(
    fake_connections,
):
    from datetime import UTC, datetime

    from ml_pipeline_pro.config import Settings
    from ml_pipeline_pro.conversation_store import TurnClaim

    model = AsyncMock()
    app = create_app(
        Settings(_env_file=None, environment="test", chat_enabled=True),
        chat_model_factory=lambda _: model,
    )
    turn = ConversationTurn(
        conversation_id="conversation",
        turn_id="turn",
        request_id="first",
        revision=1,
        status="completed",
        user_message="hello",
        correlation_id="original",
    )
    store = AsyncMock()
    store.reserve.return_value = TurnClaim(turn, None, datetime.now(UTC), True)
    app.dependency_overrides[get_conversation_store] = lambda: store
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat",
            headers={"X-Project-ID": "demo", "X-Correlation-ID": "current"},
            json={"request_id": "first", "message": "hello", "expected_revision": 0},
        )
        assert response.status_code == 200
        assert response.json()["correlation_id"] == "original"
        assert response.headers["X-Correlation-ID"] == "current"
        model.generate.assert_not_called()
        assert client.get("/api/v1/health/live").status_code == 200
    model.close.assert_awaited_once()


def test_running_action_replay_is_202_and_never_dispatches(fake_connections):
    settings, action = fixture()
    from ml_pipeline_pro.conversation_store import ActionClaim

    app = create_app(settings)
    store = AsyncMock()
    store.decide.return_value = ActionClaim(action)
    app.dependency_overrides[get_conversation_store] = lambda: store
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/conversations/conversation/actions/action/decision",
            headers={"X-Project-ID": "demo", "X-Correlation-ID": "replay"},
            json={"decision": "approve", "arguments_hash": "a" * 64},
        )
        assert response.status_code == 202 and response.json()["status"] == "running"
        assert "owner_token" not in response.text and "submission_key" not in response.text
        store.finish_action.assert_not_called()
        assert store.decide.call_args.args[0].correlation_id == "replay"


def test_native_adapter_prepares_lazily_and_saves_artifact_provenance(fake_connections):
    from tests.conversation_memory import MemoryConversations
    from tests.test_conversation_ollama import Runtime, settings

    runtime = Runtime()
    config = settings(chat_enabled=True)
    model = runtime.model(config)
    app = create_app(config, chat_model_factory=lambda _: model)
    store = MemoryConversations()
    app.dependency_overrides[get_conversation_store] = lambda: store
    with TestClient(app) as client:
        assert runtime.requests == []  # No inference dependency at startup.
        response = client.post(
            "/api/v1/chat",
            headers={"X-Project-ID": "demo"},
            json={
                "request_id": "first",
                "message": "What should I inspect?",
                "expected_revision": 0,
            },
        )
        assert response.status_code == 200 and response.json()["status"] == "completed"
        assert response.json()["model_provenance"]["artifact_digest"] == "a" * 64
        assert [request.url.path for request in runtime.requests] == [
            "/api/tags",
            "/api/show",
            "/api/version",
            "/api/chat",
        ]
    assert model._closed


def test_native_adapter_generates_draft_through_http_and_replays_without_inference(
    fake_connections,
):
    from ml_pipeline_pro.config import Settings
    from ml_pipeline_pro.conversation_ollama import OllamaConversationModel
    from tests.conversation_memory import MemoryConversations
    from tests.test_snippet_generation import Generator

    class NativeGenerator(Generator, OllamaConversationModel):
        prepare = AsyncMock()

    model = NativeGenerator()
    model.close = AsyncMock()
    app = create_app(
        Settings(_env_file=None, environment="test", chat_enabled=True),
        chat_model_factory=lambda _: model,
    )
    # Keep one store across initial request, replay and history.
    store = MemoryConversations()
    app.dependency_overrides[get_conversation_store] = lambda: store
    body = {"request_id": "draft", "message": "Generate a listing draft", "expected_revision": 0}
    with TestClient(app) as client:
        assert model.prepare.await_count == 0
        headers = {"X-Project-ID": "demo"}
        response = client.post("/api/v1/chat", headers=headers, json=body)
        assert response.status_code == 200
        saved = response.json()
        assert saved["status"] == "completed"
        assert saved["snippet"]["status"] == "validated"
        assert saved["snippet"]["review_required"] is True
        assert saved["pending_action"] is None and saved["tool_results"] == []
        assert len(model.messages) == 1
        model.generate_snippet.assert_awaited_once()
        assert model.prepare.await_count == 2  # Selection and draft are both prepared lazily.
        prepared = model.prepare.await_count
        replay = client.post("/api/v1/chat", headers=headers, json=body)
        assert replay.json() == saved
        history = client.get(
            f"/api/v1/conversations/{saved['conversation_id']}", headers=headers
        ).json()
        assert history["turns"][0]["snippet"] == saved["snippet"]
        assert len(model.messages) == 1 and model.prepare.await_count == prepared
        model.generate_snippet.assert_awaited_once()
    model.close.assert_awaited_once()

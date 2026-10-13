"""Reproduce snippet capability loss through the canonical HTTP lifespan.

Uses a scripted Ollama subclass and in-memory storage; no inference, database
operations, generated-code execution, or domain HTTP requests are performed.
"""

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_api import get_conversation_store
from ml_pipeline_pro.conversation_ollama import OllamaConversationModel
from ml_pipeline_pro.conversation_qwen_counter import QwenConversationModel
from ml_pipeline_pro.conversation_schemas import ChatRequest
from ml_pipeline_pro.conversation_service import ConversationService
from ml_pipeline_pro.main import create_app
from ml_pipeline_pro.tool_schemas import ToolContext
from tests.conversation_memory import MemoryConversations
from tests.test_conversation_service import RecordsTransport
from tests.test_snippet_generation import Generator


class ScriptedOllama(Generator, OllamaConversationModel):
    """Exercise the production isinstance/wrapper branch without model I/O."""

    async def prepare(self):
        return self


def probe():
    settings = Settings(_env_file=None, environment="test", chat_enabled=True)
    direct_model = ScriptedOllama()
    service = ConversationService(
        settings, MemoryConversations(), direct_model, RecordsTransport({})
    )
    direct = asyncio.run(
        service.chat(
            ToolContext(project_id="demo"),
            ChatRequest(
                request_id="direct", message="Generate a listing draft", expected_revision=0
            ),
        )
    )
    route_model = ScriptedOllama()
    app = create_app(settings, chat_model_factory=lambda _: route_model)
    store = MemoryConversations()
    app.dependency_overrides[get_conversation_store] = lambda: store
    with TestClient(app) as client:
        wrapper = app.state.conversation_model
        response = client.post(
            "/api/v1/chat",
            headers={"X-Project-ID": "demo"},
            json={
                "request_id": "route",
                "message": "Generate a listing draft",
                "expected_revision": 0,
            },
        )
        routed = response.json()
        result = {
            "direct_turn_status": direct.status,
            "direct_snippet_status": direct.snippet.status,
            "direct_generation_calls": direct_model.generate_snippet.await_count,
            "http_status": response.status_code,
            "http_turn_status": routed["status"],
            "http_error_code": routed["error"]["code"],
            "http_snippet_status": routed["snippet"]["status"],
            "http_validation_issues": routed["snippet"]["validation_issues"],
            "http_generation_calls": route_model.generate_snippet.await_count,
            "wrapper_type": type(wrapper).__name__,
            "wrapper_exposes_generate_snippet": callable(
                getattr(wrapper, "generate_snippet", None)
            ),
            "qwen_adapter_is_ollama_subclass": issubclass(
                QwenConversationModel, OllamaConversationModel
            ),
            "storage": "existing serial in-memory test substitute",
            "inference": "scripted; no live model",
        }
    assert direct.status == "completed" and direct.snippet.status == "validated"
    assert routed["status"] == "failed" and routed["error"]["code"] == "model_unavailable"
    assert result["direct_generation_calls"] == 1 and result["http_generation_calls"] == 0
    control_model = Generator()
    control_app = create_app(settings, chat_model_factory=lambda _: control_model)
    control_app.dependency_overrides[get_conversation_store] = MemoryConversations
    with TestClient(control_app) as client:
        response = client.post(
            "/api/v1/chat",
            headers={"X-Project-ID": "demo"},
            json={
                "request_id": "control",
                "message": "Generate a listing draft",
                "expected_revision": 0,
            },
        )
        control = response.json()
        result["non_ollama_factory_http_turn_status"] = control["status"]
        result["non_ollama_factory_http_snippet_status"] = control["snippet"]["status"]
        result["non_ollama_factory_generation_calls"] = control_model.generate_snippet.await_count
    assert control["status"] == "completed" and control["snippet"]["status"] == "validated"
    assert result["qwen_adapter_is_ollama_subclass"] is False
    return result


if __name__ == "__main__":
    observed = probe()
    output = Path("artifacts/project-audit/2026-10-13/snippet-route-probe.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(observed, indent=2))

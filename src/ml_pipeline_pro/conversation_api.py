"""Project-authenticated conversation endpoints and lifespan-owned clients."""

from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from ml_pipeline_pro.access import project_access
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_actions import ConversationActions
from ml_pipeline_pro.conversation_model import ConversationModel
from ml_pipeline_pro.conversation_ollama import OllamaConversationModel
from ml_pipeline_pro.conversation_qwen_counter import QwenConversationModel
from ml_pipeline_pro.conversation_schemas import (
    TOOL_BYTES,
    ActionDecision,
    ChatRequest,
    ConversationAction,
    ConversationHistory,
    ConversationTurn,
)
from ml_pipeline_pro.conversation_service import ConversationService
from ml_pipeline_pro.conversation_store import ConversationStore
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.tool_schemas import ResourceId, ToolContext
from ml_pipeline_pro.tool_transport import HttpToolTransport

router = APIRouter(prefix="/api/v1", tags=["conversation"])
ModelFactory = Callable[[Settings], ConversationModel]


class _LazyOllama:
    """Inspect only when generation starts; replay/decisions remain offline."""

    def __init__(self, model: OllamaConversationModel):
        self.model = model
        self.provenance = model.provenance

    async def generate(self, messages):
        await self.model.prepare()
        return await self.model.generate(messages)

    async def generate_snippet(self, messages):
        await self.model.prepare()
        return await self.model.generate_snippet(messages)

    async def generate_monitoring(self, messages):
        await self.model.prepare()
        return await self.model.generate_monitoring(messages)

    async def close(self):
        await self.model.close()


@asynccontextmanager
async def conversation_clients(
    settings: Settings,
    *,
    model_factory: ModelFactory | None = None,
) -> AsyncIterator[tuple[ConversationModel | None, HttpToolTransport | None]]:
    """Construction stays offline; disabled/unconfigured chat never breaks startup."""
    async with AsyncExitStack() as stack:
        model, transport = None, None
        if settings.chat_enabled:
            transport = await stack.enter_async_context(
                HttpToolTransport(
                    settings.chat_api_origin,
                    timeout_seconds=settings.chat_action_timeout_seconds,
                    max_response_bytes=TOOL_BYTES,
                )
            )
            if model_factory is not None or settings.chat_model is not None:
                model = (
                    model_factory(settings)
                    if model_factory is not None
                    else QwenConversationModel(settings, settings.chat_tokenizer_path)
                    if settings.chat_tokenizer_path is not None
                    else OllamaConversationModel(settings)
                )
                if isinstance(model, OllamaConversationModel):
                    model = _LazyOllama(model)
                stack.push_async_callback(model.close)
        yield model, transport


def get_conversation_store(request: Request) -> ConversationStore:
    if not hasattr(request.app.state, "conversation_store"):
        settings = request.app.state.settings
        request.app.state.conversation_store = ConversationStore(
            request.app.state.connections.mongo.get_database(settings.mongodb_database),
            settings,
        )
    return request.app.state.conversation_store


def trusted_context(request: Request, project_id: str) -> ToolContext:
    return ToolContext(
        project_id=project_id,
        api_key=request.headers.get("X-API-Key"),
        correlation_id=request.state.correlation_id,
    )


def enabled(request: Request, project_id: Annotated[str, Depends(project_access)]) -> None:
    if not request.app.state.settings.chat_enabled:
        raise ApiError(
            503, "chat_unavailable", "Conversation generation and decisions are disabled"
        )


@router.post("/chat", response_model=ConversationTurn, dependencies=[Depends(enabled)])
async def chat(
    body: ChatRequest,
    request: Request,
    response: Response,
    project_id: Annotated[str, Depends(project_access)],
    store: Annotated[ConversationStore, Depends(get_conversation_store)],
) -> ConversationTurn:
    service = ConversationService(
        request.app.state.settings,
        store,
        request.app.state.conversation_model,
        request.app.state.conversation_transport,
    )
    result = await service.chat(trusted_context(request, project_id), body)
    if result.status == "running":
        response.status_code = 202
    return result


@router.get("/conversations/{conversation_id}", response_model=ConversationHistory)
async def history(
    conversation_id: ResourceId,
    project_id: Annotated[str, Depends(project_access)],
    store: Annotated[ConversationStore, Depends(get_conversation_store)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConversationHistory:
    return await store.history(project_id, conversation_id, limit=limit, offset=offset)


@router.get(
    "/conversations/{conversation_id}/actions/{action_id}", response_model=ConversationAction
)
async def action(
    conversation_id: ResourceId,
    action_id: ResourceId,
    project_id: Annotated[str, Depends(project_access)],
    store: Annotated[ConversationStore, Depends(get_conversation_store)],
) -> ConversationAction:
    return await store.action(project_id, conversation_id, action_id)


@router.post(
    "/conversations/{conversation_id}/actions/{action_id}/decision",
    response_model=ConversationAction,
    dependencies=[Depends(enabled)],
)
async def decide(
    conversation_id: ResourceId,
    action_id: ResourceId,
    body: ActionDecision,
    request: Request,
    response: Response,
    project_id: Annotated[str, Depends(project_access)],
    store: Annotated[ConversationStore, Depends(get_conversation_store)],
) -> ConversationAction:
    service = ConversationActions(
        request.app.state.settings, store, request.app.state.conversation_transport
    )
    result = await service.decide(
        trusted_context(request, project_id), conversation_id, action_id, body
    )
    if result.status == "running":
        response.status_code = 202
    return result

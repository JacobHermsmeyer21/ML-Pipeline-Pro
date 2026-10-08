"""Model interface and native tool schemas, without inference or tool execution."""

from typing import Any, Protocol

from ml_pipeline_pro.conversation_schemas import ModelStep
from ml_pipeline_pro.tools import tool_catalog


class ConversationModel(Protocol):
    """Injected by the host; implementations own and close their inference clients."""

    provenance: dict[str, Any]

    async def generate(self, messages: list[dict[str, Any]]) -> ModelStep: ...

    async def close(self) -> None: ...


def model_tools() -> list[dict[str, Any]]:
    """Expose the existing catalog through the LangChain native tool protocol.

    This describes proposed calls only. Trusted project/auth/confirmation context
    is never model-visible, and a host dispatcher remains the execution boundary.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": item.name,
                "description": item.description,
                "parameters": item.parameters,
            },
        }
        for item in tool_catalog()
    ]

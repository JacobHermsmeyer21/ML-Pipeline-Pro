"""Exercise conversation tool contracts with synthetic data and no services."""

import asyncio
import json
from datetime import UTC, datetime

from ml_pipeline_pro.schemas import ExperimentResult
from ml_pipeline_pro.tool_schemas import ToolCall, ToolContext
from ml_pipeline_pro.tool_transport import ToolResponse
from ml_pipeline_pro.tools import ToolDispatcher


class ScriptedProvider:
    """Fixed tool calls stand in for a future model-provider adapter."""

    def calls(self) -> list[ToolCall]:
        return [
            ToolCall(name="get_experiment", arguments={"experiment_id": "demo-experiment"}),
            ToolCall(
                name="create_experiment",
                arguments={"dataset_id": "demo-dataset", "model_id": "demo-model"},
            ),
        ]


class DemoTransport:
    async def request(self, method, path, *, context, query, body) -> ToolResponse:
        if method != "GET" or path != "/api/v1/experiments/demo-experiment":
            raise RuntimeError("The demo supports only the scripted read")
        timestamp = datetime(2026, 10, 6, tzinfo=UTC)
        record = ExperimentResult(
            id="demo-experiment",
            project_id="demo",
            dataset_id="demo-dataset",
            model_id="demo-model",
            created_at=timestamp,
            updated_at=timestamp,
        )
        return ToolResponse(200, record.model_dump(mode="json"), context.correlation_id)


async def main() -> None:
    dispatcher = ToolDispatcher(DemoTransport())
    context = ToolContext(project_id="demo", correlation_id="local-tool-demo")
    results = [await dispatcher.execute(call, context) for call in ScriptedProvider().calls()]
    print(
        json.dumps(
            {
                "mode": "synthetic_contract_demo",
                "description": "Synthetic queued record; no training or provider execution.",
                "results": [result.model_dump(mode="json") for result in results],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())

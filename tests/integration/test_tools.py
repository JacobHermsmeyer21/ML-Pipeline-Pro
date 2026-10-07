"""Tool calls through HTTP to real metadata, queue, and worker services."""

import asyncio
import os
import time
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest

from ml_pipeline_pro.tool_schemas import ToolCall, ToolContext
from ml_pipeline_pro.tool_transport import HttpToolTransport
from ml_pipeline_pro.tools import ToolDispatcher
from tests.integration.helpers import api_base_url
from tests.integration.test_tuning import cleanup_project, register_inputs

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB/Redis"
    ),
    pytest.mark.skipif(
        os.getenv("MLPP_RUN_WORKER_INTEGRATION") != "1", reason="Requires queued workers"
    ),
]


def test_real_tool_submission_reads_comparison_idempotency_and_active_cancellation():
    project = f"test_tools_{uuid4().hex}"
    try:
        with httpx.Client(
            base_url=api_base_url(), headers={"X-Project-ID": project}, timeout=10
        ) as client:
            inputs = register_inputs(client)

        async def run():
            parsed = urlsplit(api_base_url())
            async with HttpToolTransport(f"{parsed.scheme}://{parsed.netloc}") as transport:
                dispatcher = ToolDispatcher(transport)

                async def execute(name, arguments, *, key=None, mutate=False):
                    result = await dispatcher.execute(
                        ToolCall(name=name, arguments=arguments),
                        ToolContext(
                            project_id=project,
                            correlation_id="live-tool-workflow",
                            allow_mutations=mutate,
                            submission_key=key,
                        ),
                    )
                    assert result.status == "succeeded", result
                    assert result.correlation_id == "live-tool-workflow"
                    assert all(item.project_id == project for item in result.evidence)
                    return result

                async def wait_for(name, record_id, statuses, deadline_seconds=90):
                    id_field = "experiment_id" if name == "get_experiment" else "tuning_job_id"
                    result = None
                    try:
                        async with asyncio.timeout(deadline_seconds):
                            while True:
                                result = await execute(name, {id_field: record_id})
                                if result.data["status"] in statuses:
                                    return result
                                await asyncio.sleep(0.1)
                    except TimeoutError:
                        pytest.fail(f"Job did not reach {statuses}: {result}")

                training_body = {**inputs, "config": {"epochs": 5, "max_runtime_seconds": 60}}
                first = await execute(
                    "create_experiment", training_body, key="training-action", mutate=True
                )
                repeated = await execute(
                    "create_experiment", training_body, key="training-action", mutate=True
                )
                assert first.data["id"] == repeated.data["id"]
                trained = await wait_for(
                    "get_experiment", first.data["id"], {"succeeded", "failed"}
                )
                assert trained.data["status"] == "succeeded"
                assert trained.data["attempts"] == 1
                assert trained.data["test_evaluated"]

                tuning_body = {
                    **training_body,
                    "objective_metric": "validation_f1",
                    "limits": {"max_trials": 2, "max_runtime_seconds": 60},
                }
                tuning = await execute(
                    "create_tuning_job", tuning_body, key="tuning-action", mutate=True
                )
                repeated = await execute(
                    "create_tuning_job", tuning_body, key="tuning-action", mutate=True
                )
                assert tuning.data["id"] == repeated.data["id"]
                tuned = await wait_for("get_tuning_job", tuning.data["id"], {"succeeded", "failed"})
                assert tuned.data["status"] == "succeeded"
                assert tuned.data["completed_trials"] == 2
                assert tuned.data["final_evaluation"] == "succeeded"
                trials = await execute("list_tuning_trials", {"tuning_job_id": tuning.data["id"]})
                assert len(trials.data["items"]) == 2
                assert all("test_f1" not in item["metrics"] for item in trials.data["items"])
                assert {ref.record_id for ref in trials.evidence if ref.kind == "trial"} == {
                    item["id"] for item in trials.data["items"]
                }
                comparison = await execute(
                    "compare_experiments",
                    {"experiment_ids": [trained.data["id"], tuned.data["best_experiment_id"]]},
                )
                assert comparison.data["metric"] == "validation_f1"
                assert sum(ref.role == "winner" for ref in comparison.evidence) == 1
                for name, arguments in [
                    ("list_datasets", {}),
                    ("get_dataset", {"dataset_id": inputs["dataset_id"]}),
                    ("list_models", {}),
                    ("get_model", {"model_id": inputs["model_id"]}),
                    (
                        "list_experiments",
                        {"model_id": inputs["model_id"], "status": "succeeded", "limit": 1},
                    ),
                    ("list_tuning_jobs", {}),
                ]:
                    assert (await execute(name, arguments)).evidence

                cancel_body = {
                    **tuning_body,
                    "config": {"epochs": 500, "max_runtime_seconds": 60},
                    "limits": {"max_trials": 50, "max_runtime_seconds": 60},
                    "search_space": {
                        "batch_size": {"choices": [1]},
                        "hidden_units": {"low": 512, "high": 512, "step": 1},
                    },
                }
                active = await execute(
                    "create_tuning_job", cancel_body, key="cancel-action", mutate=True
                )
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    active = await execute("get_tuning_job", {"tuning_job_id": active.data["id"]})
                    if active.data["status"] == "running" and active.data["scheduled_trials"] >= 1:
                        break
                    await asyncio.sleep(0.05)
                assert active.data["status"] == "running"
                assert active.data["scheduled_trials"] >= 1
                await execute(
                    "cancel_tuning_job", {"tuning_job_id": active.data["id"]}, mutate=True
                )
                cancelled = await wait_for(
                    "get_tuning_job", active.data["id"], {"cancelled"}, deadline_seconds=20
                )
                assert cancelled.data["scheduled_trials"] == active.data["scheduled_trials"]

        asyncio.run(run())
    finally:
        cleanup_project(project)

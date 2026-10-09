"""Real API idempotency, confirmed workflows, and killed chat-process recovery."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from ml_pipeline_pro.conversation_actions import ConversationActions
from ml_pipeline_pro.conversation_schemas import ActionDecision, ChatRequest
from ml_pipeline_pro.tool_schemas import ToolCall
from ml_pipeline_pro.tuning_schemas import TuningRecord
from ml_pipeline_pro.tuning_store import TuningStore
from tests.integration.helpers import integration_settings
from tests.integration.test_conversation_service import exercise
from tests.integration.test_conversation_service import pytestmark as service_marks

pytestmark = [
    *service_marks,
    pytest.mark.skipif(
        os.getenv("MLPP_RUN_WORKER_INTEGRATION") != "1",
        reason="Requires real worker integration",
    ),
]
ROOT = Path(__file__).resolve().parents[2]


async def proposal(store, context, call):
    claim = await store.reserve(
        context,
        ChatRequest(request_id="first", message="submit", expected_revision=0),
        deadline=store._now() + timedelta(seconds=60),
    )
    turn = await store.finish(
        context,
        claim,
        claim.turn.model_copy(update={"status": "awaiting_confirmation"}),
        proposal=call,
    )
    return turn.pending_action


async def inputs(client):
    dataset = await client.post(
        "/datasets",
        json={
            "name": "chat_data",
            "version": "v1",
            "uri": "classification.csv",
            "feature_columns": ["feature_1", "feature_2"],
        },
    )
    model = await client.post("/models", json={"name": "chat_model"})
    assert dataset.status_code == model.status_code == 201
    return {
        "dataset_id": dataset.json()["id"],
        "model_id": model.json()["id"],
        "config": {"epochs": 1, "max_runtime_seconds": 10},
    }


@pytest.mark.parametrize("tool", ["create_experiment", "create_tuning_job"])
def test_confirmed_real_submission_replay_retains_one_job(tool):
    async def run(settings, connections, database, store, context, client, transport):
        arguments = await inputs(client)
        if tool == "create_tuning_job":
            arguments.update(
                objective_metric="validation_f1",
                limits={"max_trials": 1, "max_runtime_seconds": 20},
            )
        action = await proposal(store, context, ToolCall(name=tool, arguments=arguments))
        service = ConversationActions(settings, store, transport)
        body = ActionDecision(decision="approve", arguments_hash=action.arguments_hash)
        result = await service.decide(context, action.conversation_id, action.action_id, body)
        assert result.status == "succeeded" and result.outcome.http_status == 202
        record_id = result.outcome.data["id"]
        assert (
            await service.decide(context, action.conversation_id, action.action_id, body) == result
        )
        path = "/experiments" if tool == "create_experiment" else "/tuning-jobs"
        page = await client.get(path)
        assert page.status_code == 200 and len(page.json()["items"]) == 1
        assert page.json()["items"][0]["id"] == record_id

    exercise(run)


def test_confirmed_cancellation_of_seeded_queued_tuning_job():
    async def run(settings, connections, database, store, context, client, transport):
        arguments = await inputs(client)
        domain = connections.mongo.get_database(integration_settings().mongodb_database)
        tuning = TuningStore(domain)
        await tuning.ensure_indexes()
        # Deliberately unqueued fixture isolates cancellation from worker timing.
        job = await tuning.jobs.insert(
            TuningRecord(
                project_id=context.project_id,
                dataset_id=arguments["dataset_id"],
                model_id=arguments["model_id"],
                submission_key="cancel-fixture",
                request_hash="a" * 64,
            )
        )
        action = await proposal(
            store, context, ToolCall(name="cancel_tuning_job", arguments={"tuning_job_id": job.id})
        )
        result = await ConversationActions(settings, store, transport).decide(
            context,
            action.conversation_id,
            action.action_id,
            ActionDecision(decision="approve", arguments_hash=action.arguments_hash),
        )
        assert result.status == "succeeded"
        assert result.outcome.data["id"] == job.id and result.outcome.data["status"] == "cancelled"
        assert (await client.get(f"/tuning-jobs/{job.id}")).json()["status"] == "cancelled"

    exercise(run)


def port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


async def ready(client, process):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        assert process.poll() is None, "Disposable API exited before readiness"
        try:
            if (await client.get("/api/v1/health/live")).status_code == 200:
                return
        except httpx.TransportError:
            pass
        await asyncio.sleep(0.05)
    raise AssertionError("Disposable API did not become ready")


def test_killed_chat_api_after_acceptance_retries_same_action_key_after_restart(tmp_path):
    async def run(settings, connections, database, store, context, client, transport):
        action = await proposal(
            store, context, ToolCall(name="create_experiment", arguments=await inputs(client))
        )
        settings = settings.model_copy(update={"chat_action_timeout_seconds": 3})
        environment = dict(os.environ)
        environment.update(
            MLPP_CHAT_ENABLED="true",
            MLPP_CHAT_ACTION_TIMEOUT_SECONDS="3",
            MLPP_CHAT_API_ORIGIN=str(client.base_url).removesuffix("/api/v1/"),
            MLPP_MONGODB_URI=settings.mongodb_uri.get_secret_value(),
            MLPP_REDIS_URL=settings.redis_url.get_secret_value(),
            MLPP_MONGODB_DATABASE=settings.mongodb_database,
        )
        signal = tmp_path / "accepted.json"
        process = None
        pending = None
        log = await asyncio.to_thread((tmp_path / "chat-process.log").open, "w", encoding="utf-8")
        route = (
            f"/api/v1/conversations/{action.conversation_id}/actions/{action.action_id}/decision"
        )
        body = {"decision": "approve", "arguments_hash": action.arguments_hash}
        original = await database.conversation_actions.find_one({"_id": action.action_id})
        try:
            for iteration in range(2):
                api_port = port()
                command = [
                    sys.executable,
                    "-m",
                    "tests.integration.conversation_crash_process",
                    "--port",
                    str(api_port),
                ]
                if iteration == 0:
                    command.extend(["--signal", str(signal)])
                process = await asyncio.to_thread(
                    subprocess.Popen,
                    command,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=ROOT,
                )
                async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{api_port}",
                    timeout=5,
                    headers={"X-Project-ID": context.project_id},
                    trust_env=False,
                ) as api:
                    await ready(api, process)
                    if iteration == 0:
                        pending = asyncio.create_task(api.post(route, json=body))
                        deadline = time.monotonic() + 10
                        for _ in range(500):
                            if (
                                await asyncio.to_thread(signal.exists)
                                or time.monotonic() >= deadline
                            ):
                                break
                            await asyncio.sleep(0.02)
                        assert await asyncio.to_thread(signal.exists), (
                            "Domain acceptance was not reached"
                        )
                        accepted_id = json.loads(
                            await asyncio.to_thread(signal.read_text, encoding="utf-8")
                        )["accepted_id"]
                        saved = await database.conversation_actions.find_one(
                            {"_id": action.action_id}
                        )
                        assert saved["public"]["status"] == "running" and saved["owner_token"]
                        process.terminate()
                        await asyncio.to_thread(process.wait, 10)
                        await asyncio.gather(pending, return_exceptions=True)
                        remaining = (saved["deadline"] - store._now()).total_seconds()
                        if remaining > 0:
                            await asyncio.sleep(remaining + 0.02)
                    else:
                        response = await api.post(route, json=body)
                        assert response.status_code == 200, response.text
                        result = response.json()
                        assert (
                            result["status"] == "succeeded"
                            and result["outcome"]["data"]["id"] == accepted_id
                        )
                        assert [attempt["status"] for attempt in result["attempts"]] == [
                            "unknown",
                            "succeeded",
                        ]
                        assert (await api.post(route, json=body)).json() == result
                if process.poll() is None:
                    process.terminate()
                    await asyncio.to_thread(process.wait, 10)
            saved = await database.conversation_actions.find_one({"_id": action.action_id})
            assert saved["submission_key"] == original["submission_key"]
            page = await client.get("/experiments")
            assert len(page.json()["items"]) == 1 and page.json()["items"][0]["id"] == accepted_id
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                await asyncio.to_thread(process.wait, 10)
            if pending and not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            log.close()

    exercise(run)

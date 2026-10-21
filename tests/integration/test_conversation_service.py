"""Scripted model with real scoped HTTP reads and transactional conversation storage."""

import asyncio
import os
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.conversation_model import ConversationModelError
from ml_pipeline_pro.conversation_schemas import ChatRequest
from ml_pipeline_pro.conversation_service import ConversationService
from ml_pipeline_pro.conversation_store import ConversationStore
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.schemas import TrainingConfig
from ml_pipeline_pro.tool_schemas import ToolContext
from ml_pipeline_pro.tool_transport import HttpToolTransport
from ml_pipeline_pro.tuning_schemas import TrialRecord, TuningRecord
from ml_pipeline_pro.tuning_store import TuningStore
from tests.integration.helpers import api_base_url, integration_settings
from tests.test_conversation_ollama import Runtime, chat_response, completion_response
from tests.test_conversation_service import ScriptedModel, call, reply

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB and API"
    ),
]


def exercise(callback):
    async def run():
        project = f"test_{uuid4().hex}"
        database_name = f"mlpp_loop_{uuid4().hex}"
        settings = integration_settings(chat_enabled=True, mongodb_database=database_name)
        async with open_connections(settings) as connections:
            database = connections.mongo.get_database(database_name)
            store = ConversationStore(database, settings)
            await store.ensure_indexes()
            context = ToolContext(project_id=project, correlation_id="loop-integration")
            async with httpx.AsyncClient(
                base_url=api_base_url(),
                headers={"X-Project-ID": project},
                trust_env=False,
                timeout=10,
            ) as client:
                async with HttpToolTransport(
                    api_base_url().removesuffix("/api/v1"), max_response_bytes=128 * 1024
                ) as transport:
                    try:
                        await callback(
                            settings, connections, database, store, context, client, transport
                        )
                    finally:
                        domain = connections.mongo.get_database(
                            integration_settings().mongodb_database
                        )
                        for collection in (
                            "datasets",
                            "models",
                            "experiments",
                            "tuning_jobs",
                            "trials",
                        ):
                            await domain[collection].delete_many({"project_id": project})
                        await connections.mongo.drop_database(database_name)

    asyncio.run(run())


def test_real_scoped_read_grounding_persistence_and_replay_need_no_second_model_call():
    async def run(settings, connections, database, store, context, client, transport):
        created = await client.post("/models", json={"name": "loop_model"})
        assert created.status_code == 201, created.text
        model_id = created.json()["id"]
        model = ScriptedModel(
            call("get_model", model_id=model_id), reply(record_id=model_id, field="name")
        )
        service = ConversationService(settings, store, model, transport)
        body = ChatRequest(
            request_id="first", message="Inspect registered model", expected_revision=0
        )
        first = await service.chat(context, body)
        assert first.status == "completed" and first.facts[0].value == "loop_model"
        restarted = ConversationService(
            settings, ConversationStore(database, settings), None, transport
        )
        assert await restarted.chat(context, body) == first
        assert len(model.messages) == 2
        with pytest.raises(ApiError) as caught:
            await store.history("foreign", first.conversation_id)
        assert caught.value.code == "conversation_not_found"

    exercise(run)


@pytest.mark.parametrize("tool", ["get_model", "create_experiment", "create_tuning_job"])
@pytest.mark.parametrize("architecture", ["mlp", "logistic_regression"])
def test_experiment_model_alias_uses_real_scoped_reads_and_canonical_saved_action(
    tool, architecture
):
    from ml_pipeline_pro.schemas import ExperimentRecord, LogisticRegressionConfig
    from ml_pipeline_pro.tracking import TrackingStore

    async def run(settings, connections, database, store, context, client, transport):
        dataset = await client.post(
            "/datasets",
            json={
                "name": "alias_data",
                "version": "v1",
                "uri": "classification.csv",
                "feature_columns": ["feature_1", "feature_2"],
            },
        )
        created = await client.post(
            "/models", json={"name": "alias_model", "architecture": architecture}
        )
        assert dataset.status_code == created.status_code == 201
        dataset_id, model_id = dataset.json()["id"], created.json()["id"]
        domain = connections.mongo.get_database(integration_settings().mongodb_database)
        tracking = TrackingStore(domain)
        await tracking.ensure_indexes()
        experiment = await tracking.experiments.insert(
            ExperimentRecord(
                project_id=context.project_id,
                dataset_id=dataset_id,
                model_id=model_id,
                submission_key="alias-fixture",
                request_hash="a" * 64,
                config=LogisticRegressionConfig(algorithm="logistic_regression")
                if architecture == "logistic_regression"
                else TrainingConfig(),
            )
        )
        arguments = {"model_id": experiment.short_id}
        if tool != "get_model":
            arguments.update(dataset_id=dataset_id, config={"max_runtime_seconds": 60})
        if tool == "create_tuning_job":
            arguments.update(
                objective_metric="validation_f1",
                limits={"max_trials": 5, "max_runtime_seconds": 300},
            )
        model = ScriptedModel(
            call(tool, **arguments), reply(record_id=model_id, field="architecture")
        )
        transport.request = AsyncMock(wraps=transport.request)
        service = ConversationService(settings, store, model, transport)
        body = ChatRequest(
            request_id="alias", message="Use the experiment's model", expected_revision=0
        )
        result = await service.chat(context, body)
        assert result.tool_results[0].data["id"] == experiment.id
        assert result.tool_results[-1].data["id"] == model_id
        if tool == "get_model":
            assert result.status == "completed" and result.facts[0].value == architecture
        elif architecture == "logistic_regression":
            assert (
                result.status == "failed" and result.error["code"] == "unsupported_model_algorithm"
            )
            assert result.pending_action is None
        else:
            assert result.status == "awaiting_confirmation"
            assert result.pending_action.tool.arguments["model_id"] == model_id
        assert all(entry.args[0] == "GET" for entry in transport.request.call_args_list)
        reads = transport.request.call_count
        restarted = ConversationService(
            settings, ConversationStore(database, settings), None, transport
        )
        assert await restarted.chat(context, body) == result
        assert transport.request.call_count == reads
        assert await domain.tuning_jobs.count_documents({"project_id": context.project_id}) == 0
        assert await domain.experiments.count_documents({"project_id": context.project_id}) == 1

    exercise(run)


def test_real_rejected_fact_persists_diagnostic_and_replays_after_restart():
    async def run(settings, connections, database, store, context, client, transport):
        created = await client.post("/models", json={"name": "diagnostic_model"})
        assert created.status_code == 201, created.text
        identity = created.json()["id"]
        model = ScriptedModel(
            call("get_model", model_id=identity),
            reply(record_id=identity, field="metrics.best_epoch"),
        )
        service = ConversationService(settings, store, model, transport)
        body = ChatRequest(request_id="diagnostic", message="inspect", expected_revision=0)
        first = await service.chat(context, body)
        assert first.status == "failed" and first.facts == []
        assert first.error["details"] == {
            "validation_stage": "evidence_resolution",
            "validation_reason": "unsupported_fact_field",
        }
        assert first.tool_results[0].status == "succeeded" and len(model.messages) == 2
        restarted_store = ConversationStore(database, settings)
        restarted = ConversationService(settings, restarted_store, None, transport)
        assert await restarted.chat(context, body) == first
        history = await restarted_store.history(context.project_id, first.conversation_id)
        assert history.turns == [first]
        assert len(model.messages) == 2
        assert await database.conversation_actions.count_documents({}) == 0
        with pytest.raises(ApiError) as caught:
            await restarted_store.history("foreign", first.conversation_id)
        assert caught.value.code == "conversation_not_found"

    exercise(run)


@pytest.mark.parametrize("invalid_fact", [False, True])
def test_native_completion_uses_real_evidence_and_persists_without_creating_actions(invalid_fact):
    async def run(settings, connections, database, store, context, client, transport):
        created = await client.post("/models", json={"name": "native_model"})
        assert created.status_code == 201, created.text
        model_id = created.json()["id"]
        arguments = {
            "message": "Inspect this registered model.",
            "citations": [model_id],
            "facts": [{"record_id": model_id, "field": "name"}],
        }
        if invalid_fact:
            arguments["facts"][0]["value"] = "forged"
        responses = [
            chat_response(
                message={
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_model",
                                "arguments": {"model_id": model_id},
                            }
                        }
                    ],
                }
            ),
            completion_response(arguments),
        ]

        async def respond(_):
            return httpx.Response(200, json=responses.pop(0))

        runtime = Runtime(overrides={"/api/chat": respond})
        transport.request = AsyncMock(wraps=transport.request)
        async with runtime.model() as model:
            service = ConversationService(
                settings.model_copy(update={"chat_max_tool_calls": 1}), store, model, transport
            )
            body = ChatRequest(request_id="native", message="Inspect model", expected_revision=0)
            first = await service.chat(context, body)
        assert first.pending_action is None
        if invalid_fact:
            assert first.status == "failed" and first.error["code"] == "model_invalid_response"
            assert first.facts == []
        else:
            assert first.status == "completed" and first.facts[0].value == "native_model"
        assert await store.actions.count_documents({}) == 0
        assert await store.turns.count_documents({}) == 1
        transport.request.assert_awaited_once()
        assert transport.request.await_args.args == ("GET", f"/api/v1/models/{model_id}")
        replay = await ConversationService(settings, store, None, transport).chat(context, body)
        assert replay == first
        assert len(runtime.token_requests) == 2

    exercise(run)


def test_fixture_validation_history_produces_bounded_saved_tuning_proposal_without_a_job():
    async def run(settings, connections, database, store, context, client, transport):
        dataset = await client.post(
            "/datasets",
            json={
                "name": "loop_data",
                "version": "v1",
                "uri": "classification.csv",
                "feature_columns": ["feature_1", "feature_2"],
            },
        )
        model_record = await client.post("/models", json={"name": "loop_model"})
        assert dataset.status_code == model_record.status_code == 201
        dataset_id, model_id = dataset.json()["id"], model_record.json()["id"]
        domain = connections.mongo.get_database(integration_settings().mongodb_database)
        tuning = TuningStore(domain)
        await tuning.ensure_indexes()
        job = await tuning.jobs.insert(
            TuningRecord(
                project_id=context.project_id,
                dataset_id=dataset_id,
                model_id=model_id,
                submission_key="history-fixture",
                request_hash="a" * 64,
            )
        )
        assert await tuning.jobs.claim(
            context.project_id, job.id, "fixture-owner", lease_seconds=30, max_attempts=3
        )
        # Fixture numbers establish grounded retrieval, not measured training quality.
        trial = await tuning.trials.insert(
            TrialRecord(
                project_id=context.project_id,
                tuning_job_id=job.id,
                number=0,
                experiment_id="fixture-experiment",
                config=TrainingConfig(learning_rate=0.02),
                parameters={"learning_rate": 0.02},
                worker_token="fixture-owner",
            )
        )
        assert await tuning.trials.claim(context.project_id, trial.id, "fixture-owner")
        assert await tuning.trials.finish(
            context.project_id,
            trial.id,
            "fixture-owner",
            values={
                "status": "succeeded",
                "objective_value": 0.82,
                "metrics": {"validation_f1": 0.82},
            },
        )
        assert await tuning.jobs.finish(
            context.project_id,
            job.id,
            "fixture-owner",
            values={"status": "succeeded", "best_trial_id": trial.id, "best_value": 0.82},
        )
        model = ScriptedModel(
            call("get_tuning_job", tuning_job_id=job.id),
            call("list_tuning_trials", tuning_job_id=job.id),
            call(
                "create_tuning_job",
                dataset_id=dataset_id,
                model_id=model_id,
                config={"max_runtime_seconds": 10},
                objective_metric="validation_f1",
                limits={"max_trials": 2, "max_runtime_seconds": 60},
                search_space={"learning_rate": {"low": 0.01, "high": 0.03}},
            ),
        )
        service = ConversationService(settings, store, model, transport)
        before = await domain.tuning_jobs.count_documents({"project_id": context.project_id})
        result = await service.chat(
            context,
            ChatRequest(
                request_id="history",
                message=(
                    "Suggest a two-trial validation search with 60 total seconds "
                    "and 10 seconds per trial using saved validation history"
                ),
                expected_revision=0,
            ),
        )
        assert result.status == "awaiting_confirmation"
        assert result.pending_action.tool.arguments["objective_metric"] == "validation_f1"
        assert result.pending_action.tool.arguments["limits"]["max_trials"] == 2
        assert len(result.tool_results) == 4 and len(model.messages) == 3
        assert any(ref.record_id == trial.id for ref in result.evidence)
        assert (
            await domain.tuning_jobs.count_documents({"project_id": context.project_id}) == before
        )
        raw = await database.conversation_actions.find_one({"_id": result.pending_action.action_id})
        assert raw["submission_key"] and "submission_key" not in result.pending_action.model_dump()

    exercise(run)


def test_overall_read_timeout_reconciles_real_turn_to_interrupted_and_reports_ids():
    class SlowRead:
        async def request(self, *args, **kwargs):
            await asyncio.sleep(2)

    async def run(settings, connections, database, store, context, client, transport):
        limited = settings.model_copy(
            update={"chat_timeout_seconds": 0.3, "chat_model_timeout_seconds": 0.1}
        )
        store = ConversationStore(database, limited)
        model = ScriptedModel(call("get_model", model_id="model"))
        service = ConversationService(limited, store, model, SlowRead())
        with pytest.raises(ApiError) as caught:
            await service.chat(
                context, ChatRequest(request_id="timeout", message="Read", expected_revision=0)
            )
        assert caught.value.code == "chat_timeout" and caught.value.status_code == 504
        history = await store.history(context.project_id, caught.value.details["conversation_id"])
        assert history.turns[0].status == "interrupted"
        assert history.turns[0].turn_id == caught.value.details["turn_id"]
        assert len(model.messages) == 1

    exercise(run)


def test_model_failure_preserves_direct_api_availability_and_saved_failure():
    async def run(settings, connections, database, store, context, client, transport):
        model = ScriptedModel(ConversationModelError("model_unavailable", "fixture model failure"))
        result = await ConversationService(settings, store, model, transport).chat(
            context, ChatRequest(request_id="unavailable", message="Read", expected_revision=0)
        )
        assert result.status == "failed" and result.error["code"] == "model_unavailable"
        assert (await client.get("/health/live")).status_code == 200
        saved = (await store.history(context.project_id, result.conversation_id)).turns[0]
        assert saved == result

    exercise(run)

"""Dataset aliases preserve canonical relationships and exact proposed requests."""

import asyncio
import hashlib
import json

import httpx
import pytest

from ml_pipeline_pro.conversation_schemas import TOOL_BYTES, ChatRequest, fingerprint
from ml_pipeline_pro.conversation_service import ConversationService
from ml_pipeline_pro.schemas import ExperimentCreate
from ml_pipeline_pro.short_ids import is_short_id
from ml_pipeline_pro.tool_schemas import ToolContext
from ml_pipeline_pro.tool_transport import HttpToolTransport
from ml_pipeline_pro.tuning_schemas import TuningCreate
from tests.conversation_memory import MemoryConversations
from tests.test_column_api import column_client as column_client
from tests.test_column_api import numeric, review, save
from tests.test_conversation_service import ScriptedModel, call, config, reply
from tests.test_tools import call as tool_call
from tests.test_tools import run_call


def test_dataset_alias_reads_tool_evidence_and_project_isolation(
    tracking_client, dataset_body, app
):
    first = tracking_client.post("/api/v1/datasets", json=dataset_body).json()
    second = tracking_client.post("/api/v1/datasets", json={**dataset_body, "version": "v2"}).json()
    assert first["short_id"] == "d1" and second["short_id"] == "d2"
    assert first["id"] != "d1" and tracking_client.get("/api/v1/datasets/d1").json() == first
    result = run_call(app, tool_call("get_dataset", dataset_id="d1"))
    assert result.data["id"] == first["id"] and result.data["short_id"] == "d1"
    assert result.evidence[0].record_id == first["id"]
    for identity in ("d1", first["id"]):
        assert (
            tracking_client.get(
                "/api/v1/datasets/" + identity, headers={"X-Project-ID": "other"}
            ).status_code
            == 404
        )
    assert tracking_client.get("/api/v1/datasets/d999").status_code == 404
    assert is_short_id("datasets", "d1")
    for invalid in ("d0", "d01", "D1", "d-1", "e1", "c1", "d" + "9" * 30):
        assert not is_short_id("datasets", invalid)


@pytest.mark.parametrize("kind", ["experiments", "tuning-jobs"])
def test_submission_by_dataset_alias_stores_canonical_id_and_original_request_hash(
    tracking_client, experiment_body, store, tuning_store, kind
):
    body = {**experiment_body, "dataset_id": "d1"}
    model = ExperimentCreate
    repository = store.experiments
    if kind == "tuning-jobs":
        body["limits"] = {"max_trials": 1, "max_runtime_seconds": 30}
        model, repository = TuningCreate, tuning_store.jobs
    response = tracking_client.post(
        f"/api/v1/{kind}", json=body, headers={"Idempotency-Key": "alias-submit"}
    )
    assert response.status_code == 202, response.text
    saved = response.json()
    assert saved["dataset_id"] == experiment_body["dataset_id"]
    expected = hashlib.sha256(
        json.dumps(model.model_validate(body).model_dump(), sort_keys=True).encode()
    ).hexdigest()
    assert repository.records[saved["id"]].request_hash == expected
    assert (
        tracking_client.post(
            f"/api/v1/{kind}", json=body, headers={"Idempotency-Key": "alias-submit"}
        ).json()
        == saved
    )
    conflict = tracking_client.post(
        f"/api/v1/{kind}",
        json={**body, "dataset_id": experiment_body["dataset_id"]},
        headers={"Idempotency-Key": "alias-submit"},
    )
    assert (
        conflict.status_code == 409 and conflict.json()["error"]["code"] == "idempotency_conflict"
    )
    assert len(repository.records) == 1


def test_agent_understands_d1_inspection_and_preserves_d1_in_training_proposal(
    app, experiment_body
):
    async def run():
        async with HttpToolTransport(
            "http://testserver",
            transport=httpx.ASGITransport(app=app),
            max_response_bytes=TOOL_BYTES,
        ) as transport:
            context = ToolContext(project_id="demo")
            conversations = MemoryConversations()
            model = ScriptedModel(
                call("get_dataset", dataset_id="d1"),
                reply(record_id=experiment_body["dataset_id"], field="row_counts.train"),
            )
            turn = await ConversationService(config(), conversations, model, transport).chat(
                context,
                ChatRequest(
                    request_id="inspect", message="Inspect dataset d1", expected_revision=0
                ),
            )
            assert turn.status == "completed" and turn.facts[0].value == 80
            assert turn.facts[0].record_id == experiment_body["dataset_id"]
            model = ScriptedModel(
                call(
                    "create_experiment",
                    dataset_id="d1",
                    model_id=experiment_body["model_id"],
                    config={"max_runtime_seconds": 10},
                )
            )
            turn = await ConversationService(config(), conversations, model, transport).chat(
                context,
                ChatRequest(request_id="propose", message="Train dataset d1", expected_revision=0),
            )
            assert turn.status == "awaiting_confirmation"
            action = turn.pending_action
            assert action.tool.arguments["dataset_id"] == "d1"
            assert action.arguments_hash == fingerprint(action.tool.model_dump())
            assert any(
                e.kind == "dataset" and e.record_id == experiment_body["dataset_id"]
                for e in turn.evidence
            )

    asyncio.run(run())


def test_column_alias_replays_after_parent_erasure(column_client, store):
    parent = numeric(column_client)
    body = review(column_client, parent, ["feature_2"])
    response = column_client.post("/api/v1/datasets/d1/columns", json=body)
    assert response.status_code == 201, response.text
    child = response.json()
    assert child["short_id"] == "d2" and child["selection"]["parent_id"] == parent["id"]
    assert save(column_client, parent, body).json() == child
    del store.datasets.records[parent["id"]]
    replay = column_client.post("/api/v1/datasets/d1/columns", json=body)
    assert replay.status_code == 200 and replay.json() == child
    assert column_client.get("/api/v1/datasets/d1").status_code == 404
    assert column_client.get("/api/v1/datasets/d2").json() == child

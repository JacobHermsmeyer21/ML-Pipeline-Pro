"""Short references preserve canonical API/tool identities and exact-body replay."""

import asyncio
import json

import pytest

from ml_pipeline_pro.conversation_guidance import requested_facts
from ml_pipeline_pro.schemas import ExperimentResult
from ml_pipeline_pro.short_ids import MAX_NUMBER, is_short_id
from ml_pipeline_pro.tool_schemas import ToolContext, ToolFailure
from ml_pipeline_pro.tools import ToolDispatcher
from tests.test_tools import StubTransport, call, run_call


@pytest.mark.parametrize(
    "kind,good,bad",
    [
        ("experiments", "e1", ["1", "c1", "e0", "e01", "e-1", "E1", "e1/", "e١"]),
        ("conversations", "c2", ["2", "e2", "c0", "c02", "c+2", "C2"]),
    ],
)
def test_alias_grammar_is_positive_ascii_bounded_and_kind_specific(kind, good, bad):
    assert is_short_id(kind, good)
    prefix = good[0]
    assert is_short_id(kind, prefix + str(MAX_NUMBER))
    for identity in [*bad, prefix + str(MAX_NUMBER + 1), prefix + "1" * 10000]:
        assert not is_short_id(kind, identity)


def test_requested_alias_facts_require_matching_canonical_tool_evidence():
    user = {
        "role": "user",
        "content": "Inspect experiment e1. Return a verified metrics.validation_f1 fact.",
    }
    result = {
        "status": "succeeded",
        "data": {
            "id": "canonical-run",
            "short_id": "e1",
            "project_id": "demo",
            "metrics": {"validation_f1": 0.8},
        },
        "evidence": [
            {
                "kind": "experiment",
                "role": "record",
                "record_id": "canonical-run",
                "project_id": "demo",
            }
        ],
    }

    def messages():
        return [user, {"role": "tool", "name": "get_experiment", "content": json.dumps(result)}]

    assert requested_facts(messages()) == [
        {"record_id": "canonical-run", "field": "metrics.validation_f1"}
    ]
    result["evidence"][0]["record_id"] = "e1"
    assert requested_facts(messages()) == []
    result["evidence"][0]["record_id"] = "canonical-run"
    result["data"]["short_id"] = "e2"
    assert requested_facts(messages()) == []


@pytest.mark.parametrize("project,alias", [("foreign", "e1"), ("demo", "e2"), ("demo", None)])
def test_alias_resolution_rejects_unrelated_records_before_canonical_dispatch(project, alias):
    record = ExperimentResult(
        id="unrelated",
        project_id=project,
        short_id=alias,
        dataset_id="dataset",
        model_id="model",
    )
    transport = StubTransport(record.model_dump(mode="json"))
    result = asyncio.run(
        ToolDispatcher(transport).execute(
            call("get_experiment", experiment_id="e1"), ToolContext(project_id="demo")
        )
    )
    assert isinstance(result, ToolFailure)
    assert result.error.code == "tool_validation_error"
    assert len(transport.calls) == 1 and transport.calls[0][1] == "/api/v1/experiments/e1"


def test_experiment_aliases_work_in_api_tools_comparison_and_project_scope(
    tracking_client, experiment_body, store, app
):
    first = tracking_client.post(
        "/api/v1/experiments", json=experiment_body, headers={"Idempotency-Key": "short-first"}
    ).json()
    second = tracking_client.post(
        "/api/v1/experiments", json=experiment_body, headers={"Idempotency-Key": "short-second"}
    ).json()
    assert first["short_id"] == "e1" and second["short_id"] == "e2"
    assert first["id"] != "e1" and second["id"] != "e2"
    assert tracking_client.get("/api/v1/experiments/e1").json() == first
    replay = tracking_client.post(
        "/api/v1/experiments", json=experiment_body, headers={"Idempotency-Key": "short-first"}
    ).json()
    assert replay == first and len(store.experiments.records) == 2
    for record, score in ((first, 0.8), (second, 0.7)):
        saved = store.experiments.records[record["id"]]
        saved.status = "succeeded"
        saved.metrics = {"validation_f1": score}
    inspected = run_call(app, call("get_experiment", experiment_id="e1"))
    assert inspected.data["id"] == first["id"]
    assert inspected.evidence[0].record_id == first["id"]
    compared = run_call(app, call("compare_experiments", experiment_ids=["e1", "e2"]))
    assert compared.data["best_experiment_id"] == first["id"]
    duplicate = run_call(app, call("compare_experiments", experiment_ids=["e1", first["id"]]))
    assert isinstance(duplicate, ToolFailure) and duplicate.error.code == "tool_validation_error"
    response = tracking_client.get(
        "/api/v1/experiments/compare",
        params=[("experiment_id", "e1"), ("experiment_id", first["id"])],
    )
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_comparison"
    assert (
        tracking_client.get("/api/v1/experiments/e1", headers={"X-Project-ID": "other"}).status_code
        == 404
    )
    assert tracking_client.get("/api/v1/experiments/e999").status_code == 404


def test_deleted_alias_is_never_rebound_to_new_experiment(tracking_client, experiment_body, store):
    first = tracking_client.post(
        "/api/v1/experiments", json=experiment_body, headers={"Idempotency-Key": "old"}
    ).json()
    del store.experiments.records[first["id"]]
    new = tracking_client.post(
        "/api/v1/experiments", json=experiment_body, headers={"Idempotency-Key": "new"}
    ).json()
    assert new["short_id"] == "e2"
    assert tracking_client.get("/api/v1/experiments/e1").status_code == 404
    assert asyncio.run(store.experiments.get("demo", "e2")).id == new["id"]

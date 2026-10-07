import asyncio

import httpx
import pytest
from kombu.exceptions import OperationalError
from pydantic import SecretStr, ValidationError

from ml_pipeline_pro.schemas import ExperimentRecord
from ml_pipeline_pro.tool_schemas import ToolCall, ToolContext
from ml_pipeline_pro.tool_transport import HttpToolTransport, ToolResponse
from ml_pipeline_pro.tools import ToolDispatcher, tool_catalog
from ml_pipeline_pro.tuning_schemas import TrialRecord

KEY = "tool-project-secret-key"


class StubTransport:
    def __init__(self, payload=None, status_code=200):
        self.calls = []
        self.payload = payload
        self.status_code = status_code

    async def request(self, method, path, *, context, query, body):
        self.calls.append((method, path, query, body))
        return ToolResponse(self.status_code, self.payload, context.correlation_id)


def context(**kwargs):
    return ToolContext(project_id="demo", correlation_id="tool-test", **kwargs)


def call(name, **arguments):
    return ToolCall(name=name, arguments=arguments)


def run_call(app, request, execution_context=None):
    async def run():
        async with HttpToolTransport(
            "http://testserver", transport=httpx.ASGITransport(app=app, raise_app_exceptions=False)
        ) as transport:
            return await ToolDispatcher(transport).execute(request, execution_context or context())

    return asyncio.run(run())


def training_arguments(inputs):
    return {**inputs, "config": {"max_runtime_seconds": 60}}


def tuning_arguments(inputs):
    return {
        **training_arguments(inputs),
        "objective_metric": "validation_f1",
        "limits": {"max_trials": 2, "max_runtime_seconds": 60},
    }


def test_catalog_advertises_required_inputs_defaults_and_only_supported_operations():
    catalog = {item.name: item for item in tool_catalog()}
    assert len(catalog) == 13
    assert {name for name, item in catalog.items() if item.mutating} == {
        "create_experiment",
        "create_tuning_job",
        "cancel_tuning_job",
    }
    assert catalog["list_experiments"].defaults == {
        "limit": 50,
        "offset": 0,
        "status": None,
        "model_id": None,
    }
    training = catalog["create_experiment"].parameters
    assert set(training["required"]) == {"dataset_id", "model_id", "config"}
    assert training["$defs"]["ToolTrainingConfig"]["required"] == ["max_runtime_seconds"]
    tuning = catalog["create_tuning_job"].parameters
    assert {"config", "limits", "objective_metric"}.issubset(tuning["required"])
    assert tuning["$defs"]["ToolTuningLimits"]["required"] == ["max_trials", "max_runtime_seconds"]
    assert catalog["create_tuning_job"].defaults["search_space"]["batch_size"] == {
        "choices": [8, 16, 32]
    }
    assert all(item.parameters["additionalProperties"] is False for item in catalog.values())
    catalog["list_models"].parameters.clear()
    assert tool_catalog()[2].parameters["type"] == "object"


@pytest.mark.parametrize(
    "tool_call",
    [
        call("delete_models"),
        {"name": "list_models", "arguments": {}, "project_id": "other"},
        call("list_models", project_id="other"),
        call("list_models", api_key=KEY),
        call("list_models", headers={"X-Project-ID": "other"}),
        call("list_models", origin="https://other.example"),
        call("list_models", correlation_id="override"),
        call("list_models", submission_key="override"),
        call("list_models", limit=0),
        call("list_models", limit=101),
        call("list_models", limit=True),
        call("list_models", offset=-1),
        call("get_experiment", experiment_id="../models"),
        call("get_experiment", experiment_id="id%2Fmodels"),
        call("get_experiment", experiment_id="id?project=other"),
        call("get_experiment", experiment_id="id\n"),
        call("compare_experiments", experiment_ids=["one", "one"]),
        call("compare_experiments", experiment_ids=["one"]),
        call("compare_experiments", experiment_ids=["one", "two"], metric="test_f1"),
        call("create_experiment", dataset_id="dataset", model_id="model"),
        call("create_experiment", dataset_id="dataset", model_id="model", config={}),
        call(
            "create_experiment",
            dataset_id="dataset",
            model_id="model",
            config={"max_runtime_seconds": 601},
        ),
        call(
            "create_tuning_job",
            dataset_id="dataset",
            model_id="model",
            config={"max_runtime_seconds": 60},
            limits={"max_trials": 2, "max_runtime_seconds": 60},
        ),
        call(
            "create_tuning_job",
            dataset_id="dataset",
            model_id="model",
            config={"max_runtime_seconds": 60},
            objective_metric="validation_f1",
            limits={"max_trials": 2},
        ),
        call(
            "create_tuning_job",
            dataset_id="dataset",
            model_id="model",
            config={"max_runtime_seconds": 60},
            objective_metric="validation_f1",
            limits={"max_runtime_seconds": 60},
        ),
        call(
            "create_tuning_job",
            dataset_id="dataset",
            model_id="model",
            config={"max_runtime_seconds": 60},
            objective_metric="validation_f1",
            limits={"max_trials": 2, "max_runtime_seconds": 60, "concurrency": 2},
        ),
    ],
)
def test_invalid_provider_calls_never_dispatch(tool_call):
    transport = StubTransport()
    result = asyncio.run(
        ToolDispatcher(transport).execute(
            tool_call, context(allow_mutations=True, submission_key="action-key")
        )
    )
    assert result.status == "error"
    assert result.error.code in {"tool_not_found", "tool_validation_error"}
    assert result.correlation_id == result.error.correlation_id == "tool-test"
    assert transport.calls == []
    assert KEY not in result.model_dump_json()


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("create_experiment", training_arguments({"dataset_id": "dataset", "model_id": "model"})),
        ("create_tuning_job", tuning_arguments({"dataset_id": "dataset", "model_id": "model"})),
        ("cancel_tuning_job", {"tuning_job_id": "job"}),
    ],
)
def test_mutation_requires_host_permission(name, arguments):
    transport = StubTransport()
    result = asyncio.run(
        ToolDispatcher(transport).execute(call(name, **arguments), context(submission_key="action"))
    )
    assert result.error.code == "tool_mutation_denied"
    assert transport.calls == []


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("create_experiment", training_arguments({"dataset_id": "dataset", "model_id": "model"})),
        ("create_tuning_job", tuning_arguments({"dataset_id": "dataset", "model_id": "model"})),
    ],
)
def test_submission_requires_host_key(name, arguments):
    transport = StubTransport()
    result = asyncio.run(
        ToolDispatcher(transport).execute(call(name, **arguments), context(allow_mutations=True))
    )
    assert result.error.code == "tool_submission_key_required"
    assert transport.calls == []


def test_scripted_provider_stub_returns_public_record_evidence_without_services():
    record = ExperimentRecord(
        project_id="demo",
        dataset_id="dataset",
        model_id="model",
        submission_key="private-key",
        request_hash="0" * 64,
    )
    # Match the public HTTP response rather than handing persistence fields to a provider.
    public = {
        key: value
        for key, value in record.model_dump(mode="json").items()
        if key
        not in {
            "submission_key",
            "request_hash",
            "worker_token",
            "lease_expires_at",
            "last_dispatch_at",
            "evaluate_test",
            "selection_metric",
        }
    }
    transport = StubTransport(public)
    provider_calls = [call("get_experiment", experiment_id=record.id)]
    result = asyncio.run(ToolDispatcher(transport).execute(provider_calls[0], context()))
    assert result.status == "succeeded"
    assert result.data["id"] == result.evidence[0].record_id == record.id
    assert result.data["status"] == "queued"
    assert "private-key" not in result.model_dump_json()


def test_all_read_tools_use_real_app_filters_pagination_and_evidence(
    app, store, publisher, experiment_body, tuning_store
):
    inputs = experiment_body
    first = run_call(
        app,
        call("create_experiment", **training_arguments(inputs)),
        context(allow_mutations=True, submission_key="first"),
    )
    second = run_call(
        app,
        call("create_experiment", **training_arguments(inputs)),
        context(allow_mutations=True, submission_key="second"),
    )
    for result, score in ((first, 0.6), (second, 0.9)):
        record = store.experiments.records[result.data["id"]]
        record.status = "succeeded"
        record.metrics = {
            "validation_f1": score,
            "validation_accuracy": score,
            "test_f1": 1 - score,
        }
    tuning = run_call(
        app,
        call("create_tuning_job", **tuning_arguments(inputs)),
        context(allow_mutations=True, submission_key="tuning"),
    )
    job_id = tuning.data["id"]
    trial = TrialRecord(
        project_id="demo",
        tuning_job_id=job_id,
        number=0,
        experiment_id=first.data["id"],
        parameters={},
        config={},
    )
    tuning_store.trials.records[trial.id] = trial
    requests = [
        call("list_datasets"),
        call("get_dataset", dataset_id=inputs["dataset_id"]),
        call("list_models"),
        call("get_model", model_id=inputs["model_id"]),
        call(
            "list_experiments", status="succeeded", model_id=inputs["model_id"], limit=1, offset=1
        ),
        call("get_experiment", experiment_id=first.data["id"]),
        call("compare_experiments", experiment_ids=[first.data["id"], second.data["id"]]),
        call("list_tuning_jobs"),
        call("get_tuning_job", tuning_job_id=job_id),
        call("list_tuning_trials", tuning_job_id=job_id),
    ]
    results = [run_call(app, request) for request in requests]
    assert all(result.status == "succeeded" for result in results), results
    assert all(result.evidence for result in results)
    assert all(
        reference.project_id == "demo" for result in results for reference in result.evidence
    )
    assert len(results[4].data["items"]) == 1
    assert results[4].data["limit"] == results[4].data["offset"] == 1
    comparison = results[6]
    assert comparison.data["best_experiment_id"] == second.data["id"]
    assert {item.record_id for item in comparison.evidence if item.role == "winner"} == {
        second.data["id"]
    }
    assert results[9].data["items"][0]["id"] == trial.id
    assert {item.kind for item in results[9].evidence} == {"trial", "experiment", "tuning_job"}
    assert "worker_token" not in str(results)
    assert run_call(app, call("list_experiments", status="queued")).data["items"] == []


@pytest.mark.parametrize("name", ["create_experiment", "create_tuning_job"])
def test_submission_retries_preserve_one_record_and_conflicts(
    app, experiment_body, store, tuning_store, name
):
    arguments = (
        training_arguments(experiment_body)
        if name == "create_experiment"
        else tuning_arguments(experiment_body)
    )
    execution_context = context(allow_mutations=True, submission_key="same-action")
    first = run_call(app, call(name, **arguments), execution_context)
    repeated = run_call(app, call(name, **arguments), execution_context)
    assert first.status == repeated.status == "succeeded"
    assert first.data["id"] == repeated.data["id"]
    arguments["config"]["seed"] = 43
    conflict = run_call(app, call(name, **arguments), execution_context)
    assert conflict.http_status == 409
    assert conflict.error.code == "idempotency_conflict"
    repository = store.experiments if name == "create_experiment" else tuning_store.jobs
    assert len(repository.records) == 1


@pytest.mark.parametrize(
    "name,detail", [("create_experiment", "experiment_id"), ("create_tuning_job", "tuning_job_id")]
)
def test_queue_failure_returns_safe_saved_job_id_for_retry(
    app, experiment_body, publisher, tuning_store, name, detail
):
    arguments = (
        training_arguments(experiment_body)
        if name == "create_experiment"
        else tuning_arguments(experiment_body)
    )
    execution_context = context(allow_mutations=True, submission_key="queue-retry")
    publisher.error = OperationalError("redis://user:private-password@host")
    failure = run_call(app, call(name, **arguments), execution_context)
    assert failure.http_status == 503
    assert failure.error.code == "queue_unavailable"
    saved_id = failure.error.details[detail]
    assert "private-password" not in failure.model_dump_json()
    publisher.error = None
    success = run_call(app, call(name, **arguments), execution_context)
    assert success.data["id"] == saved_id


def test_cancellation_reuses_existing_lifecycle_and_needs_no_submission_key(
    app, experiment_body, tuning_store
):
    submission = run_call(
        app,
        call("create_tuning_job", **tuning_arguments(experiment_body)),
        context(allow_mutations=True, submission_key="cancel"),
    )
    request = call("cancel_tuning_job", tuning_job_id=submission.data["id"])
    cancelled = run_call(app, request, context(allow_mutations=True))
    assert cancelled.data["status"] == "cancelled"
    assert run_call(app, request, context(allow_mutations=True)).data["status"] == "cancelled"
    record = tuning_store.jobs.records[submission.data["id"]]
    record.status = "running"
    assert (
        run_call(app, request, context(allow_mutations=True)).data["status"] == "cancel_requested"
    )
    record.status = "succeeded"
    conflict = run_call(app, request, context(allow_mutations=True))
    assert conflict.http_status == 409
    assert conflict.error.code == "tuning_job_complete"


@pytest.mark.parametrize("reference", ["dataset_id", "model_id"])
@pytest.mark.parametrize("name", ["create_experiment", "create_tuning_job"])
def test_authorized_submissions_reject_foreign_references(
    app, experiment_body, store, tuning_store, reference, name
):
    app.state.settings.project_api_keys = {"demo": SecretStr(KEY)}
    repository = store.datasets if reference == "dataset_id" else store.models
    repository.records[experiment_body[reference]].project_id = "other"
    arguments = (
        training_arguments(experiment_body)
        if name == "create_experiment"
        else tuning_arguments(experiment_body)
    )
    result = run_call(
        app,
        call(name, **arguments),
        context(api_key=KEY, allow_mutations=True, submission_key="foreign"),
    )
    assert result.http_status == 404
    assert result.error.code == (
        "dataset_not_found" if reference == "dataset_id" else "model_not_found"
    )
    assert store.experiments.records == tuning_store.jobs.records == {}


def test_keys_and_project_scoping_are_enforced_at_api_boundary(app, experiment_body):
    app.state.settings.project_api_keys = {
        "demo": SecretStr(KEY),
        "other": SecretStr("other-project-secret-key"),
    }
    denied = run_call(
        app, call("get_dataset", dataset_id=experiment_body["dataset_id"]), context(api_key="wrong")
    )
    assert denied.http_status == 403
    assert denied.error.code == "project_access_denied"
    execution_context = ToolContext(
        project_id="other", api_key="other-project-secret-key", correlation_id="foreign-read"
    )
    missing = run_call(
        app, call("get_dataset", dataset_id=experiment_body["dataset_id"]), execution_context
    )
    assert missing.http_status == 404
    assert missing.error.code == "dataset_not_found"
    assert missing.correlation_id == missing.error.correlation_id == "foreign-read"
    assert run_call(app, call("list_datasets"), execution_context).data["items"] == []


@pytest.mark.parametrize(
    "defect,code",
    [
        ("dataset", "dataset_mismatch"),
        ("status", "experiment_not_comparable"),
        ("metric", "experiment_not_comparable"),
    ],
)
def test_comparison_reaches_domain_rejection_with_valid_tool_arguments(
    app, experiment_body, store, defect, code
):
    ids = []
    for key in ("one", "two"):
        result = run_call(
            app,
            call("create_experiment", **training_arguments(experiment_body)),
            context(allow_mutations=True, submission_key=key),
        )
        record = store.experiments.records[result.data["id"]]
        record.status = "succeeded"
        record.metrics = {"validation_f1": 0.8}
        ids.append(record.id)
    if defect == "dataset":
        store.experiments.records[ids[1]].dataset_id = "different-dataset"
    elif defect == "status":
        store.experiments.records[ids[1]].status = "running"
    else:
        store.experiments.records[ids[1]].metrics = {}
    result = run_call(app, call("compare_experiments", experiment_ids=ids))
    assert result.http_status == 409
    assert result.error.code == code


def test_trusted_context_hides_credentials_and_rejects_header_injection():
    execution_context = context(api_key=KEY, submission_key="caller-owned")
    assert KEY not in repr(execution_context)
    assert KEY not in execution_context.model_dump_json()
    assert "caller-owned" not in execution_context.model_dump_json()
    with pytest.raises(ValidationError):
        context(api_key="secret\r\nX-Project-ID: other")
    with pytest.raises(ValidationError):
        context(allow_mutations="true")

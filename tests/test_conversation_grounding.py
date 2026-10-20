import pytest

from ml_pipeline_pro.conversation_grounding import EvidenceLedger
from ml_pipeline_pro.conversation_schemas import FactRequest, ModelReply
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.schemas import ModelRecord
from ml_pipeline_pro.tool_schemas import EvidenceReference, ToolSuccess
from ml_pipeline_pro.tuning_schemas import TrialResult


def success(record, kind, *, related=None):
    return ToolSuccess(
        tool_name="fixture",
        correlation_id="fixture",
        http_status=200,
        data=record.model_dump(mode="json"),
        evidence=[
            EvidenceReference(kind=kind, record_id=record.id, project_id=record.project_id),
            *(related or []),
        ],
    )


def test_related_id_can_be_cited_but_its_unfetched_record_fields_cannot_be_invented():
    from ml_pipeline_pro.schemas import TrainingConfig

    trial = TrialResult(
        id="trial",
        project_id="demo",
        tuning_job_id="job",
        number=0,
        experiment_id="experiment",
        parameters={},
        config=TrainingConfig(),
    )
    result = success(
        trial,
        "trial",
        related=[
            EvidenceReference(kind="tuning_job", record_id="job", project_id="demo", role="parent")
        ],
    )
    ledger = EvidenceLedger("demo")
    ledger.add(result)
    assert ledger.resolve(ModelReply(message="", citations=["job"])) == []
    with pytest.raises(ApiError):
        ledger.resolve(ModelReply(message="", facts=[FactRequest(record_id="job", field="status")]))


def test_colliding_record_ids_across_kinds_are_rejected_for_fact_resolution():
    record = ModelRecord(id="same", project_id="demo", name="model")
    ledger = EvidenceLedger("demo")
    ledger.add(success(record, "model"))
    ledger.add(success(record, "dataset"))
    with pytest.raises(ApiError):
        ledger.resolve(ModelReply(message="", facts=[FactRequest(record_id="same", field="name")]))


def test_foreign_and_missing_identity_evidence_are_rejected():
    record = ModelRecord(id="model", project_id="foreign", name="model")
    with pytest.raises(ApiError):
        EvidenceLedger("demo").add(success(record, "model"))
    record.project_id = "demo"
    result = success(record, "model")
    result.data.pop("created_at")
    with pytest.raises(ApiError):
        EvidenceLedger("demo").add(result)


def test_latest_successful_snapshot_wins_without_aliasing_the_saved_tool_result():
    record = ModelRecord(id="model", project_id="demo", name="old")
    first = success(record, "model")
    ledger = EvidenceLedger("demo")
    ledger.add(first)
    record.name = "new"
    ledger.add(success(record, "model"))
    facts = ledger.resolve(
        ModelReply(message="", facts=[FactRequest(record_id="model", field="name")])
    )
    assert facts[0].value == "new"
    assert first.data["name"] == "old"


def test_available_references_use_the_resolver_and_exclude_unsupported_and_missing_values():
    from ml_pipeline_pro.schemas import ExperimentResult

    record = ExperimentResult(
        id="run",
        project_id="demo",
        dataset_id="dataset",
        model_id="model",
        metrics={"validation_f1": 0, "test_f1": 0.9, "best_epoch": 99},
    )
    result = success(record, "experiment")
    result.data["config"]["seed"] = {"untrusted": "not a scalar"}
    result.data["config"].pop("batch_size")
    ledger = EvidenceLedger("demo")
    assert ledger.available_facts() == []
    ledger.add(result)
    references = ledger.available_facts()
    fields = {ref.field for ref in references}
    assert "metrics.validation_f1" in fields
    assert not fields & {
        "metrics.test_f1",
        "metrics.best_epoch",
        "config.seed",
        "config.batch_size",
    }
    assert references == sorted(references, key=lambda ref: (ref.record_id, ref.field))
    facts = ledger.resolve(ModelReply(message="", facts=references))
    assert len(facts) == len(references)
    assert next(f.value for f in facts if f.field == "metrics.validation_f1") == 0
    assert all(set(ref.model_dump()) == {"record_id", "field"} for ref in references)


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        (ModelReply(message="", citations=["unknown"]), "unknown_citation"),
        (
            ModelReply(message="", facts=[FactRequest(record_id="model", field="name")]),
            "nonscalar_fact",
        ),
        (
            ModelReply(message="", facts=[FactRequest(record_id="missing", field="name")]),
            "ambiguous_record",
        ),
    ],
)
def test_evidence_reason_codes_identify_the_actual_rejection(reply, reason):
    result = success(ModelRecord(id="model", project_id="demo", name="model"), "model")
    result.data["name"] = {"hostile": "value"}
    ledger = EvidenceLedger("demo")
    ledger.add(result)
    with pytest.raises(ApiError) as caught:
        ledger.resolve(reply)
    assert caught.value.details == {
        "validation_stage": "evidence_resolution",
        "validation_reason": reason,
    }


def test_ambiguous_records_and_unfetched_related_records_have_no_available_facts():
    record = ModelRecord(id="same", project_id="demo", name="model")
    ledger = EvidenceLedger("demo")
    related = EvidenceReference(kind="model", record_id="parent", project_id="demo", role="parent")
    ledger.add(success(record, "model", related=[related]))
    assert all(ref.record_id == "same" for ref in ledger.available_facts())
    ledger.add(success(record, "dataset"))
    assert ledger.available_facts() == []
    assert ledger.resolve(ModelReply(message="", citations=["parent"])) == []

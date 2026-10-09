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

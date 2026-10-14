import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_model import ConversationModelError
from ml_pipeline_pro.main import create_monitoring_app
from ml_pipeline_pro.monitoring import MonitoringStore, get_monitoring_store, metrics, summarize
from ml_pipeline_pro.monitoring_schemas import (
    MonitoringAdvice,
    MonitoringStep,
    ObservationCreate,
    ObservationRecord,
)
from ml_pipeline_pro.tracking import get_store
from tests.memory import MemoryRepository
from tests.test_conversation_ollama import Runtime, chat_response, settings

NOW = datetime.now(UTC)


def record(**values):
    return ObservationRecord(
        project_id="demo",
        sample_id="sample",
        model_version_id="version",
        observed_at=NOW,
        latency_ms=1,
        input_hash="a" * 64,
        **values,
    )


def test_empty_unknown_labels_threshold_and_partial_window_are_explicit():
    empty = summarize([], "version", 300, NOW)
    assert empty.issue == "unknown" and empty.availability == "missing"
    assert empty.labeled_accuracy is None and empty.mean_latency_ms is None
    values = [record() for _ in range(101)]
    values[0].latency_ms = 150
    values[0].fault = "seeded_latency"
    values[1].prediction_correct = False
    values[2].prediction_correct = True
    values[3].outcome = "error"
    summary = summarize(values, "version", 300, NOW)
    assert summary.partial and summary.sample_count == 100
    assert summary.mean_latency_ms == pytest.approx(2.49)
    assert summary.max_latency_ms == 150 and summary.error_count == 1
    assert summary.labeled_count == 2 and summary.labeled_accuracy == 0.5
    assert summary.seeded_count == 1 and summary.issue == "latency_threshold_exceeded"
    output = metrics(values, NOW).decode()
    assert "mlpp_monitoring_partial 1.0" in output
    assert 'mlpp_workload_labeled_accuracy{model_version_id="version"} 0.5' in output
    output = metrics([record()], NOW).decode()
    assert "mlpp_workload_labeled_accuracy{" not in output


@pytest.mark.parametrize(
    "values",
    [
        {"latency_ms": float("nan")},
        {"latency_ms": -1},
        {"outcome": "error", "prediction_correct": True},
        {"fault": "inference_error", "outcome": "success"},
    ],
)
def test_observation_rejects_nonfinite_or_inconsistent_measurements(values):
    data = {
        "sample_id": "sample",
        "model_version_id": "version",
        "observed_at": NOW,
        "latency_ms": 1,
        **values,
    }
    with pytest.raises(ValidationError):
        ObservationCreate(**data)


def test_immutable_sample_id_replay_conflict_and_project_isolation():
    async def run():
        store = object.__new__(MonitoringStore)
        store.observations = MemoryRepository(("id",))
        body = ObservationCreate(
            sample_id="sample", model_version_id="version", observed_at=NOW, latency_ms=1
        )
        first = await store.insert("demo", body)
        assert await store.insert("demo", body) == first
        assert (await store.insert("foreign", body)).id != first.id
        from ml_pipeline_pro.errors import ApiError

        with pytest.raises(ApiError) as caught:
            await store.insert("demo", body.model_copy(update={"latency_ms": 2}))
        assert caught.value.code == "observation_conflict"
        assert first.observed_at.microsecond % 1000 == 0

    asyncio.run(run())


def test_diagnosis_public_provenance_redacts_nested_configured_secrets(fake_connections):
    secret = "monitoring-private-key"
    sample = record()
    model = SimpleNamespace(
        provenance={"model_tag": "test:" + secret, "packages": {"fixture": secret}},
        close=AsyncMock(),
        generate_monitoring=AsyncMock(
            return_value=MonitoringStep(
                advice=MonitoringAdvice(
                    interpretation="Inspect the declared delay.",
                    observation_ids=[sample.id],
                    proposed_checks=["inspect_seeded_delay"],
                ),
                usage={"input_tokens": 10, "output_tokens": 20},
                provenance={"protocol": "monitoring"},
            )
        ),
    )
    app = create_monitoring_app(
        Settings(_env_file=None, chat_enabled=True, project_api_keys={"demo": secret}),
        chat_model_factory=lambda settings: model,
    )
    app.dependency_overrides[get_monitoring_store] = lambda: SimpleNamespace(
        window=AsyncMock(return_value=[sample])
    )
    app.dependency_overrides[get_store] = lambda: SimpleNamespace(
        versions=SimpleNamespace(get=AsyncMock(return_value=object()))
    )
    with TestClient(app) as client:
        result = client.post(
            "/api/v1/monitoring/model-versions/version/diagnosis",
            headers={"X-Project-ID": "demo", "X-API-Key": secret},
        )
        assert result.status_code == 200
        assert secret not in result.text and "[REDACTED]" in result.text
        assert result.json()["review_required"] is True
    model.close.assert_awaited_once()


def test_monitoring_factory_owns_only_monitoring_and_enforces_project_before_storage(
    fake_connections,
):
    app = create_monitoring_app(
        Settings(_env_file=None, project_api_keys={"demo": "long-demo-test-key"})
    )
    paths = set(app.openapi()["paths"])
    assert "/api/v1/monitoring/observations" in paths
    assert "/api/v1/experiments" not in paths and "/api/v1/tuning-jobs" not in paths
    with TestClient(app) as client:
        assert client.get("/api/v1/monitoring/metrics").status_code == 422
        assert (
            client.get("/api/v1/monitoring/metrics", headers={"X-Project-ID": "demo"}).status_code
            == 403
        )
    assert fake_connections.closed


@pytest.mark.parametrize("foreign", [False, True])
def test_actual_sdk_monitoring_has_no_tools_and_rejects_foreign_citations(foreign):
    async def run():
        advice = {
            "interpretation": "Declared seeded delay; inspect it before diagnosing a regression.",
            "observation_ids": ["foreign" if foreign else "sample"],
            "proposed_checks": ["inspect_seeded_delay"],
        }
        runtime = Runtime(
            chat_response(message={"role": "assistant", "content": json.dumps(advice)})
        )
        async with runtime.model(settings()) as model:
            messages = [{"role": "user", "content": json.dumps({"observation_ids": ["sample"]})}]
            if foreign:
                with pytest.raises(ConversationModelError) as caught:
                    await model.generate_monitoring(messages)
                assert caught.value.code == "model_invalid_response"
            else:
                step = await model.generate_monitoring(messages)
                assert step.advice.observation_ids == ["sample"]
                payload = json.loads(runtime.requests[-1].content)
                assert payload["tools"] == []
                assert payload["format"]["properties"]["observation_ids"]["items"]["enum"] == [
                    "sample"
                ]
                assert runtime.token_requests[-1] == payload

    asyncio.run(run())

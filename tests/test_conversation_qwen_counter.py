"""Fail-closed profile checks and retained real-runtime rendering regressions."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_model import ConversationModelError
from ml_pipeline_pro.conversation_qwen_counter import (
    MODEL_TAG,
    PROFILE_IDENTITY,
    PROFILES,
    TOKENIZER_MAX_BYTES,
    QwenConversationModel,
    QwenInputCounter,
    render_qwen_request,
)

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures/qwen_runtime_render.json").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case", FIXTURES)
def test_render_matches_retained_real_runtime_including_schema_numbers_and_unicode(case):
    assert render_qwen_request(case["request"]) == case["runtime_rendered_prompt"]


@pytest.mark.parametrize("field", ["model_tag", *PROFILE_IDENTITY])
@pytest.mark.parametrize("tag", PROFILES)
def test_wrong_artifact_runtime_or_template_rejects_before_loading_a_tokenizer(
    field, tag, tmp_path
):
    provenance = {"model_tag": tag, **PROFILES[tag], field: "unverified"}
    with pytest.raises(ConversationModelError, match="profile is unavailable") as caught:
        QwenInputCounter(provenance, tmp_path / "absent.json")
    assert caught.value.code == "model_unavailable"


@pytest.mark.parametrize(
    "data", [b"{}", b"x" * (TOKENIZER_MAX_BYTES + 1)], ids=["wrong-checksum", "oversized"]
)
def test_wrong_or_oversized_tokenizer_rejects_without_parsing(data, tmp_path):
    path = tmp_path / "tokenizer.json"
    path.write_bytes(data)
    with pytest.raises(ConversationModelError, match="profile is unavailable"):
        QwenInputCounter({"model_tag": MODEL_TAG, **PROFILE_IDENTITY}, path)


@pytest.mark.parametrize(
    "change",
    [
        {"model": "other-model"},
        {"messages": [{"role": "user", "content": "No explicit system"}]},
        {"think": True},
        {"messages": [{"role": "system", "content": "hello", "images": ["image"]}]},
        {"messages": [{"role": "system", "content": "x" * (64 * 1024)}]},
        {"messages": [{"role": "system", "content": "hello"}, {"role": "unknown", "content": "x"}]},
    ],
)
def test_unsupported_or_oversized_payload_never_returns_a_countable_prompt(change):
    payload = {"model": MODEL_TAG, "messages": [{"role": "system", "content": "hello"}]}
    with pytest.raises(ValueError):
        render_qwen_request({**payload, **change})


def test_unrepresentable_integer_in_tool_arguments_fails_closed():
    payload = {
        "model": MODEL_TAG,
        "messages": [
            {"role": "system", "content": "hello"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "get_model", "arguments": {"seed": 2**53 + 1}}}
                ],
            },
        ],
    }
    with pytest.raises(ValueError, match="exact profile range"):
        render_qwen_request(payload)


def test_lazy_adapter_missing_configuration_and_closed_use_never_construct_clients(
    monkeypatch, tmp_path
):
    constructors = []
    monkeypatch.setattr(
        "ml_pipeline_pro.conversation_qwen_counter.OllamaConversationModel",
        lambda *args, **kwargs: constructors.append((args, kwargs)),
    )

    async def run():
        model = QwenConversationModel(Settings(_env_file=None), tmp_path / "absent.json")
        assert constructors == []
        with pytest.raises(ConversationModelError):
            await model.generate([])
        await model.close()
        configured = QwenConversationModel(
            Settings(_env_file=None, chat_model=MODEL_TAG), tmp_path / "absent.json"
        )
        await configured.close()
        with pytest.raises(ConversationModelError):
            await configured.generate([])
        assert constructors == []

    asyncio.run(run())


def test_lazy_adapter_rejects_unverified_counter_before_inference_and_closes_clients(
    monkeypatch, tmp_path
):
    native = AsyncMock()
    native.provenance = {"model_tag": MODEL_TAG, **PROFILE_IDENTITY}
    monkeypatch.setattr(
        "ml_pipeline_pro.conversation_qwen_counter.OllamaConversationModel",
        lambda *args, **kwargs: native,
    )

    async def run():
        model = QwenConversationModel(
            Settings(_env_file=None, chat_model=MODEL_TAG), tmp_path / "absent.json"
        )
        with pytest.raises(ConversationModelError):
            await model.generate([])
        native.prepare.assert_awaited_once()
        native.generate.assert_not_called()
        assert model.provenance["artifact_digest"] == PROFILE_IDENTITY["artifact_digest"]
        await model.close()
        native.close.assert_awaited_once()

    asyncio.run(run())

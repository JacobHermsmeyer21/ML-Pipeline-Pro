"""Explicit factory for the pinned local Qwen profile; setup downloads are manual."""

from pathlib import Path

from ml_pipeline_pro.conversation_qwen_counter import QwenInputCounter


def create_counter(provenance):
    path = Path(__file__).resolve().parents[1] / ".tools/local-model-setup/tokenizer.json"
    return QwenInputCounter(provenance, path)

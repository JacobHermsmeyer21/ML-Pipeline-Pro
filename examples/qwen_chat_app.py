"""Explicit opt-in app factory for the inspected local Qwen counter profiles."""

from pathlib import Path

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_qwen_counter import QwenConversationModel
from ml_pipeline_pro.main import create_app as base_app


def create_app():
    tokenizer_path = Path(__file__).resolve().parents[1] / ".tools/local-model-setup/tokenizer.json"
    return base_app(
        Settings(
            chat_backend="ollama",
        ),
        chat_model_factory=lambda settings: QwenConversationModel(settings, tokenizer_path),
    )

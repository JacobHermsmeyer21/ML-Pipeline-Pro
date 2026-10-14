"""Host monitoring API with the pinned local Qwen counter; weights stay external."""

from pathlib import Path

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_qwen_counter import QwenConversationModel
from ml_pipeline_pro.main import create_monitoring_app


def create_app():
    return create_monitoring_app(
        Settings(),
        chat_model_factory=lambda settings: QwenConversationModel(
            settings,
            Path(__file__).resolve().parents[1] / ".tools/local-model-setup/tokenizer.json",
        ),
    )

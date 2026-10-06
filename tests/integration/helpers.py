"""Default local endpoints, with overrides for an isolated validation stack."""

import os

from ml_pipeline_pro.config import Settings


def integration_settings(**overrides) -> Settings:
    values = {
        "mongodb_uri": os.getenv("MLPP_TEST_MONGODB_URI", "mongodb://127.0.0.1:27017"),
        "redis_url": os.getenv("MLPP_TEST_REDIS_URL", "redis://127.0.0.1:6379/0"),
        **overrides,
    }
    return Settings(_env_file=None, **values)


def api_base_url() -> str:
    return os.getenv("MLPP_TEST_API_BASE_URL", "http://127.0.0.1:8000/api/v1")

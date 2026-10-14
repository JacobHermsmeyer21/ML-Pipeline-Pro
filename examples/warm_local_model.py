"""Explicitly load an installed local artifact before a bounded classroom demo."""

import argparse
import json

import httpx

from ml_pipeline_pro.config import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--origin", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    settings = Settings(_env_file=None, chat_model=args.model, chat_model_origin=args.origin)
    with httpx.Client(
        base_url=settings.chat_model_origin, timeout=120, trust_env=False, follow_redirects=False
    ) as client:
        tags = client.get("/api/tags")
        tags.raise_for_status()
        if not any(item["name"] == settings.chat_model for item in tags.json()["models"]):
            raise ValueError("Explicit model is not installed; this helper never pulls it")
        response = client.post(
            "/api/generate",
            json={
                "model": settings.chat_model,
                "prompt": "",
                "stream": False,
                "keep_alive": "30m",
                "options": {"num_ctx": settings.chat_context_tokens},
            },
        )
        response.raise_for_status()
        result = response.json()
        assert result["done"] is True and result["response"] == ""
        print(
            json.dumps(
                {
                    "model": settings.chat_model,
                    "operation": "explicit artifact load",
                    "load_duration_ns": result.get("load_duration"),
                    "generated_text": False,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

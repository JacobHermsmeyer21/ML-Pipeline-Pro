"""Create an explicit local template profile from already installed Qwen weights."""

import argparse
import hashlib
from pathlib import Path

import httpx

from ml_pipeline_pro.conversation_qwen_counter import (
    JSON_TOOLS_14B_TAG,
    JSON_TOOLS_TAG,
    PROFILES,
)
from ml_pipeline_pro.conversation_schemas import fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-model", choices=["7b", "14b"], required=True)
    args = parser.parse_args()
    source_tag = f"qwen2.5:{args.base_model}-instruct-q4_K_M"
    target_tag = JSON_TOOLS_TAG if args.base_model == "7b" else JSON_TOOLS_14B_TAG
    source_digest = {
        "7b": "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e",
        "14b": "7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6",
    }[args.base_model]
    template = Path(__file__).with_name("qwen-json-tools.gotmpl").read_text(encoding="utf-8")
    if hashlib.sha256(template.encode()).hexdigest() != (
        "1964b20ffb81926f0de5bf8e3e05ef6070a8be230bd0d0d0f228055b60d41400"
    ):
        raise RuntimeError("Pinned local template was changed")
    with httpx.Client(
        base_url="http://127.0.0.1:11434", trust_env=False, follow_redirects=False, timeout=60
    ) as client:
        response = client.get("/api/version")
        response.raise_for_status()
        if response.json()["version"] != "0.40.2":
            raise RuntimeError("This counter profile requires Ollama 0.40.2")
        response = client.get("/api/tags")
        response.raise_for_status()
        installed = {item["name"]: item["digest"] for item in response.json()["models"]}
        if source_tag not in installed:
            raise RuntimeError(f"Install {source_tag} explicitly before creating this profile")
        if installed[source_tag] != source_digest:
            raise RuntimeError("Installed source tag does not match the pinned artifact")
        if (
            target_tag in installed
            and installed[target_tag] != PROFILES[target_tag]["artifact_digest"]
        ):
            raise RuntimeError("Target tag already names another artifact; inspect it before setup")
        if target_tag not in installed:
            response = client.post(
                "/api/create",
                json={
                    "model": target_tag,
                    "from": source_tag,
                    "template": template,
                    "stream": False,
                },
            )
            response.raise_for_status()
        response = client.get("/api/tags")
        response.raise_for_status()
        actual = next(
            item["digest"] for item in response.json()["models"] if item["name"] == target_tag
        )
        response = client.post("/api/show", json={"model": target_tag})
        response.raise_for_status()
        if actual != PROFILES[target_tag]["artifact_digest"] or (
            fingerprint(response.json()["template"]) != PROFILES[target_tag]["template_hash"]
        ):
            raise RuntimeError("Created profile does not match the verified counter identity")
    print(f"Created {target_tag} with verified digest {actual}")


if __name__ == "__main__":
    main()

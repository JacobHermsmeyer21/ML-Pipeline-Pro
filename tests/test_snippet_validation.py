import json

import pytest
from pydantic import ValidationError

from ml_pipeline_pro.snippet_schemas import SNIPPET_BYTES, SnippetDraft, SnippetRequest
from ml_pipeline_pro.snippet_validation import request_shape, validate_snippet


def request(profile="list_experiments"):
    inputs = {}
    if profile == "compare_experiments":
        inputs = {"experiment_ids": ["exp-a", "exp-b"], "metric": "validation_f1"}
    if profile in ("create_experiment", "create_tuning_job"):
        inputs = {
            "dataset_id": "dataset",
            "model_id": "model",
            "config": {"max_runtime_seconds": 10},
        }
    if profile == "create_tuning_job":
        inputs.update(
            objective_metric="validation_f1", limits={"max_trials": 2, "max_runtime_seconds": 40}
        )
    return SnippetRequest(profile=profile, inputs=inputs).normalized()


def example(value=None):
    value = value or request()
    method, path, query, body = request_shape(value)
    headers = (
        '{"X-Project-ID": os.environ["MLPP_PROJECT_ID"], "X-API-Key": os.environ["MLPP_API_KEY"]'
    )
    if method == "post":
        headers += ', "Idempotency-Key": os.environ["MLPP_SUBMISSION_KEY"]'
    headers += "}"
    argument = "params=" + repr(query) if query is not None else "json=" + repr(body)
    return (
        "import os\nimport httpx\n"
        f"with httpx.Client(base_url=os.environ['MLPP_API_ORIGIN'], headers={headers}, "
        "timeout=10, follow_redirects=False, trust_env=False) as client:\n"
        f"    response = client.{method}({path!r}, {argument})\n"
        "    response.raise_for_status()\n"
        "    data = response.json()\n"
    )


@pytest.mark.parametrize(
    "profile", ["list_experiments", "compare_experiments", "create_experiment", "create_tuning_job"]
)
def test_each_profile_accepts_exact_api_shape_and_explicit_supplied_limits(profile):
    value = request(profile)
    assert validate_snippet(example(value), value) == []


@pytest.mark.parametrize(
    "replacement",
    [
        ("import os", "import subprocess"),
        ("import os", "import os as system"),
        ("import os", "from os import environ"),
        ("timeout=10", "timeout=True"),
        ("timeout=10", "timeout=31"),
        ("follow_redirects=False", "follow_redirects=True"),
        ("trust_env=False", "trust_env=True"),
        ("os.environ['MLPP_API_ORIGIN']", "'https://attacker.example'"),
        ('os.environ["MLPP_API_KEY"]', "'hardcoded-secret'"),
        ("'/api/v1/experiments'", "'/api/v1/models'"),
        ("client.get", "getattr(client, 'get')"),
        ("response.raise_for_status()", "exec('pass')"),
        ("response.raise_for_status()", "response.close()"),
        ("    response.raise_for_status()\n", ""),
        ("    data = response.json()", "    data = response.text"),
        ("    data = response.json()", "    data = response.json()\n    open('file', 'w')"),
        (
            "    data = response.json()",
            "    data = response.json()\n    client.get('/api/v1/models')",
        ),
        ("    data = response.json()", "    data = response.json()\n    while True: pass"),
        (
            "    response.raise_for_status()",
            "    response = 'overwritten'\n    response.raise_for_status()",
        ),
        ("import httpx", "import httpx\nsecret = 'unused-hardcoded-secret'"),
    ],
)
def test_unsupported_code_reaches_validator_and_rejects_without_execution(replacement):
    code = example().replace(*replacement)
    assert code != example()
    assert validate_snippet(code, request()) == ["snippet_grammar_or_api_invalid"]


@pytest.mark.parametrize("changed", ["10", "20", "True"])
def test_tuning_total_budget_cannot_be_replaced_by_per_trial_budget_or_boolean(changed):
    value = request("create_tuning_job")
    code = example(value).replace("'max_runtime_seconds': 40", f"'max_runtime_seconds': {changed}")
    assert validate_snippet(code, value) == ["snippet_grammar_or_api_invalid"]


def test_submission_requires_environment_key_and_canonical_body():
    value = request("create_experiment")
    code = example(value)
    assert validate_snippet(
        code.replace(', "Idempotency-Key": os.environ["MLPP_SUBMISSION_KEY"]', ""), value
    )
    assert validate_snippet(code.replace("'dataset_id': 'dataset'", "'dataset_id': 'other'"), value)


@pytest.mark.parametrize("code", ["", "x" * (SNIPPET_BYTES + 1), "é" * (SNIPPET_BYTES // 2 + 1)])
def test_size_is_decoded_utf8_bytes_before_parsing(code):
    assert validate_snippet(code, request()) == ["snippet_size_invalid"]


def test_exact_byte_limit_and_duplicate_dictionary_keys():
    code = example()
    boundary = code + "#" + "x" * (SNIPPET_BYTES - len(code.encode()) - 1)
    assert validate_snippet(boundary, request()) == []
    assert validate_snippet(boundary + "x", request()) == ["snippet_size_invalid"]
    assert validate_snippet(code.replace("'limit': 50", "'limit': 50, 'limit': 1"), request())


def test_explicit_submission_inputs_and_review_flag_are_required():
    with pytest.raises(ValidationError):
        SnippetRequest(profile="create_tuning_job", inputs={}).normalized()
    with pytest.raises(ValidationError):
        SnippetDraft(profile="list_experiments", status="validated", review_required=False)
    assert '"review_required": true' in json.dumps(
        SnippetDraft(profile="list_experiments", status="rejected").model_dump()
    )

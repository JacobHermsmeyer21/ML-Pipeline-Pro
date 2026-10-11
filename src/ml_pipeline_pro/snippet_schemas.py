"""Reviewable snippet contracts; model text never grants execution authority."""

from typing import Any, Literal

from pydantic import Field

from ml_pipeline_pro.schemas import RequestModel
from ml_pipeline_pro.tool_schemas import (
    CompareArguments,
    CreateExperimentArguments,
    CreateTuningArguments,
    ListExperimentsArguments,
)

SNIPPET_BYTES = 8 * 1024
SnippetProfile = Literal[
    "list_experiments", "compare_experiments", "create_experiment", "create_tuning_job"
]
PROFILE_INPUTS = {
    "list_experiments": ListExperimentsArguments,
    "compare_experiments": CompareArguments,
    "create_experiment": CreateExperimentArguments,
    "create_tuning_job": CreateTuningArguments,
}


class SnippetRequest(RequestModel):
    profile: SnippetProfile
    inputs: dict[str, Any] = Field(default_factory=dict)

    def normalized(self) -> "SnippetRequest":
        return self.model_copy(
            update={
                "inputs": PROFILE_INPUTS[self.profile]
                .model_validate(self.inputs)
                .model_dump(mode="json", exclude_none=True)
            }
        )


class SnippetCandidate(RequestModel):
    """Only code comes from the generator; validation/provenance come from the host."""

    code: str


class SnippetDraft(RequestModel):
    profile: SnippetProfile
    status: Literal["validated", "rejected"]
    review_required: Literal[True] = True
    code: str | None = None
    validation_issues: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


def snippet_tool_schema() -> dict[str, Any]:
    """Advertise per-profile typed contracts through the SDK's retained $defs."""
    schema = SnippetRequest.model_json_schema()
    definitions = {}
    descriptions = []
    for profile, model in PROFILE_INPUTS.items():
        inputs = model.model_json_schema()
        definitions.update(inputs.pop("$defs", {}))
        definitions[model.__name__] = inputs
        descriptions.append(f"{profile}: {model.__name__}")
    schema["$defs"] = definitions
    schema["properties"]["inputs"]["description"] = (
        "An object following the profile's typed schema in $defs: "
        + "; ".join(descriptions)
        + ". Keep config and limits as NESTED objects, never dotted property names. "
        "Submission requires config.max_runtime_seconds; tuning additionally requires "
        "objective_metric and limits.max_trials/max_runtime_seconds. "
        "Missing fields produce clarification, never invented budgets."
    )
    return schema

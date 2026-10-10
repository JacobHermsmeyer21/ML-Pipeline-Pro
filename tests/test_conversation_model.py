from langchain_core.utils.function_calling import convert_to_openai_tool

from ml_pipeline_pro.conversation_model import model_tools, native_conversation_tools
from ml_pipeline_pro.conversation_schemas import ModelReply
from ml_pipeline_pro.tools import tool_catalog


def test_native_tools_remain_langchain_compatible_and_require_explicit_budgets():
    tools = model_tools()
    assert {tool["function"]["name"] for tool in tools} == {item.name for item in tool_catalog()}
    assert len(tools) == 13
    for tool in tools:
        assert convert_to_openai_tool(tool) == tool
        parameters = tool["function"]["parameters"]
        assert (
            not {"project_id", "api_key", "submission_key", "allow_mutations"}
            & parameters["properties"].keys()
        )
    experiment = next(
        tool["function"] for tool in tools if tool["function"]["name"] == "create_experiment"
    )
    tuning = next(
        tool["function"] for tool in tools if tool["function"]["name"] == "create_tuning_job"
    )
    assert {"dataset_id", "model_id", "config"} <= set(experiment["parameters"]["required"])
    assert (
        "max_runtime_seconds" in experiment["parameters"]["$defs"]["ToolTrainingConfig"]["required"]
    )
    assert {"objective_metric", "limits", "config"} <= set(tuning["parameters"]["required"])
    assert {"max_trials", "max_runtime_seconds"} <= set(
        tuning["parameters"]["$defs"]["ToolTuningLimits"]["required"]
    )


def test_mutating_tool_metadata_is_fresh_and_cannot_modify_the_catalog():
    tools = model_tools()
    tools[0]["function"]["parameters"]["properties"]["api_key"] = {"type": "string"}
    assert "api_key" not in model_tools()[0]["function"]["parameters"]["properties"]


def test_native_completion_is_reply_schema_and_never_a_public_domain_tool():
    native = native_conversation_tools()
    functions = {tool["function"]["name"]: tool["function"] for tool in native}
    assert len(native) == len(functions) == 14
    assert set(functions) == {item.name for item in tool_catalog()} | {"finish_conversation"}
    assert functions["finish_conversation"]["parameters"] == ModelReply.model_json_schema()
    for tool in native:
        assert convert_to_openai_tool(tool) == tool
    for domain in tool_catalog():
        assert functions[domain.name]["parameters"] == domain.parameters
        if domain.mutating:
            assert "later exact-action human confirmation" in functions[domain.name]["description"]
    native[-1]["function"]["parameters"]["properties"]["api_key"] = {"type": "string"}
    assert "api_key" not in native_conversation_tools()[-1]["function"]["parameters"]["properties"]

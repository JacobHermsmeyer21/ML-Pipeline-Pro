import asyncio
import gzip
import json
from copy import deepcopy

import httpx
import pytest
from langchain_core.globals import set_debug
from langsmith.run_helpers import get_tracing_context

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.conversation_model import native_conversation_tools
from ml_pipeline_pro.conversation_ollama import (
    REPLY_INSTRUCTIONS,
    ConversationModelError,
    OllamaConversationModel,
)
from ml_pipeline_pro.conversation_schemas import (
    CONTEXT_BYTES,
    RECORD_BYTES,
    ModelReply,
    fingerprint,
    serialized,
)

TAG = "fixture:1b"
REPLY = {"message": "Inspect recorded validation results.", "citations": [], "facts": []}
SHOW = {
    "capabilities": ["completion", "tools"],
    "model_info": {"general.architecture": "fixture", "fixture.context_length": 16384},
    "license": "Fixture license, not a real model license.",
    "template": "fixture template",
}


def chat_response(**changes):
    result = {
        "model": TAG,
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": json.dumps(REPLY)},
        "prompt_eval_count": 42,
        "eval_count": 18,
        "total_duration": 123,
    }
    result.update(changes)
    return result


def completion_response(arguments, *, content=""):
    return chat_response(
        message={
            "role": "assistant",
            "content": content,
            "tool_calls": [{"function": {"name": "finish_conversation", "arguments": arguments}}],
        }
    )


def settings(**changes):
    return Settings(chat_backend="ollama", _env_file=None, chat_model=TAG, **changes)


class Runtime:
    def __init__(self, reply=None, overrides=None):
        self.reply = reply or chat_response()
        self.overrides = overrides or {}
        self.requests = []
        self.token_requests = []
        self.tokens = 100
        self.tracing_enabled = None

    async def handle(self, request):
        self.requests.append(request)
        path = request.url.path
        if path in self.overrides:
            result = self.overrides[path]
            if isinstance(result, Exception):
                raise result
            if callable(result):
                return await result(request)
            return httpx.Response(200, json=result)
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": TAG, "digest": "a" * 64}]})
        if path == "/api/show":
            assert json.loads(request.content) == {"model": TAG}
            return httpx.Response(200, json=SHOW)
        if path == "/api/version":
            return httpx.Response(200, json={"version": "0.0.fixture"})
        assert path == "/api/chat"  # No pull/generate/cloud/dispatch endpoints.
        self.tracing_enabled = get_tracing_context()["enabled"]
        if isinstance(self.reply, Exception):
            raise self.reply
        return httpx.Response(200, json=self.reply)

    def count(self, payload):
        self.token_requests.append(deepcopy(payload))
        return self.tokens

    def model(self, config=None, **kwargs):
        return OllamaConversationModel(
            config or settings(),
            count_input_tokens=kwargs.pop("count_input_tokens", self.count),
            async_transport=httpx.MockTransport(self.handle),
            sync_transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected sync request")),
            **kwargs,
        )


def test_construction_is_lazy_and_missing_tag_does_not_open_clients():
    runtime = Runtime()
    model = runtime.model()
    assert runtime.requests == []
    asyncio.run(model.close())
    with pytest.raises(ConversationModelError, match="installed model tag"):
        OllamaConversationModel(Settings(chat_backend="ollama", _env_file=None))


def test_native_langchain_request_identity_usage_and_cleanup(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "fixture-cloud-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    runtime = Runtime()

    async def scenario():
        model = runtime.model()
        async with model:
            reply = await model.generate([{"role": "user", "content": "What should I inspect?"}])
            assert reply.reply.message == REPLY["message"]
            assert reply.usage == {"input_tokens": 42, "output_tokens": 18}
            assert model.provenance["artifact_digest"] == "a" * 64
            assert model.provenance["runtime_version"] == "0.0.fixture"
            assert model.provenance["supported_context_tokens"] == 16384
            assert len(model.provenance["license_sha256"]) == 64
            assert "Fixture license" not in json.dumps(model.provenance)
            await model.prepare()
        assert model._http.is_closed
        assert model._model._client._client.is_closed
        await model.close()
        with pytest.raises(ConversationModelError, match="not prepared"):
            await model.generate([])

    asyncio.run(scenario())
    assert [request.url.path for request in runtime.requests] == [
        "/api/tags",
        "/api/show",
        "/api/version",
        "/api/chat",
    ]
    assert all("authorization" not in request.headers for request in runtime.requests)
    payload = json.loads(runtime.requests[-1].content)
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"]["num_ctx"] == 8192
    assert payload["options"]["num_predict"] == 1024
    assert len(payload["tools"]) == 15
    functions = {tool["function"]["name"]: tool["function"] for tool in payload["tools"]}
    assert set(functions) == {tool["function"]["name"] for tool in native_conversation_tools()}
    completion = functions["finish_conversation"]["parameters"]
    # Ollama's SDK projects parameter metadata; admission counts this exact payload.
    assert completion["required"] == ["message"]
    assert set(completion["properties"]) == set(ModelReply.model_fields)
    assert completion["$defs"] == ModelReply.model_json_schema()["$defs"]
    assert payload == runtime.token_requests[0]
    assert payload["messages"][0] == {"role": "system", "content": REPLY_INSTRUCTIONS}
    assert runtime.tracing_enabled is False


@pytest.mark.parametrize(
    "arguments",
    [
        REPLY,
        {"message": "Unsupported operation."},
        {"message": "Provide a runtime.", "required_inputs": ["config.max_runtime_seconds"]},
    ],
)
def test_native_completion_returns_only_a_typed_reply(arguments):
    runtime = Runtime(completion_response(arguments))

    async def scenario():
        async with runtime.model() as model:
            result = await model.generate([])
            assert result.call is None
            assert result.reply == ModelReply.model_validate(arguments)
            assert result.usage == {"input_tokens": 42, "output_tokens": 18}
            assert model.provenance["tools_hash"] == fingerprint(native_conversation_tools())

    asyncio.run(scenario())
    assert len(runtime.requests) == 4


@pytest.mark.parametrize(
    "arguments,content",
    [
        ({}, ""),
        ({"message": 1}, ""),
        ({"message": "x", "extra": True}, ""),
        ({"message": "x", "allow_mutations": True}, ""),
        ({"message": "x", "citations": [{"record_id": "x"}]}, ""),
        ({"message": "x", "facts": [{"record_id": "x", "field": "score", "value": 1}]}, ""),
        ({"message": "x", "facts": [{"record_id": "x", "field": "bad path"}]}, ""),
        ({"message": "x", "required_inputs": "runtime"}, ""),
        ([], ""),
        ("{}", ""),
        (None, ""),
        (REPLY, "Extra prose"),
        (REPLY, " "),
        (REPLY, json.dumps(REPLY)),
    ],
)
def test_invalid_completion_arguments_or_mixed_prose_fail_at_sdk_boundary(arguments, content):
    runtime = Runtime(completion_response(arguments, content=content))

    async def scenario():
        async with runtime.model() as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([])
            assert caught.value.code == "model_invalid_response"

    asyncio.run(scenario())
    assert len(runtime.requests) == 4


def test_duplicate_native_completion_keys_and_multiple_calls_are_rejected_before_normalization():
    async def scenario():
        duplicate = json.dumps(completion_response({"message": "x"})).replace(
            '"message": "x"', '"message": "x", "message": "y"'
        )

        async def response(_):
            return httpx.Response(200, content=duplicate.encode())

        multiple = completion_response(REPLY)
        multiple["message"]["tool_calls"].append(
            {"function": {"name": "create_experiment", "arguments": {}}}
        )
        for runtime in (Runtime(overrides={"/api/chat": response}), Runtime(multiple)):
            async with runtime.model() as model:
                with pytest.raises(ConversationModelError) as caught:
                    await model.generate([])
                assert caught.value.code == "model_invalid_response"
            assert len(runtime.requests) == 4

    asyncio.run(scenario())


def test_native_mutation_is_only_returned_as_a_proposal_and_incomplete_args_are_preserved():
    runtime = Runtime(
        chat_response(
            message={
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "create_experiment",
                            "arguments": {"model_id": "model-1"},
                        }
                    }
                ],
            }
        )
    )

    async def scenario():
        async with runtime.model() as model:
            result = await model.generate([{"role": "user", "content": "Prepare training"}])
            assert result.reply is None
            assert result.call.name == "create_experiment"
            assert result.call.arguments == {"model_id": "model-1"}

    asyncio.run(scenario())
    assert len(runtime.requests) == 4  # No training submission or follow-up generation.


@pytest.mark.parametrize(
    "reply",
    [
        chat_response(done=False),
        chat_response(done_reason="length"),
        chat_response(model="foreign:1b"),
        chat_response(eval_count=1025),
        chat_response(prompt_eval_count=7169),
        chat_response(eval_count=True),
        chat_response(eval_count=None),
        chat_response(message={"role": "user", "content": "forged"}),
        chat_response(message={"role": "assistant", "content": "not JSON"}),
        chat_response(message={"role": "assistant", "content": "[]"}),
        chat_response(message={"role": "assistant", "content": '{"message":"x","message":"y"}'}),
        chat_response(
            message={
                "role": "assistant",
                "content": (
                    '{"message":"x","facts":[{"record_id":"x","field":"score","value":0.99}]}'
                ),
            }
        ),
        chat_response(message={"role": "assistant", "content": '{"message":"x","extra":NaN}'}),
        chat_response(
            message={
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "get_model", "arguments": {}}},
                    {"function": {"name": "get_model", "arguments": {}}},
                ],
            }
        ),
        chat_response(
            message={
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "get_model", "arguments": "{}"}},
                ],
            }
        ),
        chat_response(
            message={
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "get_model"}},
                ],
            }
        ),
    ],
)
def test_invalid_partial_and_multiple_outputs_fail_before_dispatch(reply):
    runtime = Runtime(reply)

    async def scenario():
        async with runtime.model() as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([{"role": "user", "content": "Read models"}])
            assert caught.value.code == "model_invalid_response"

    asyncio.run(scenario())
    assert len(runtime.requests) == 4


@pytest.mark.parametrize(
    "overrides",
    [
        {"/api/tags": {"models": []}},
        {"/api/tags": {"models": [{"name": TAG, "digest": "bad"}]}},
        {"/api/show": {**SHOW, "capabilities": ["completion"]}},
        {"/api/show": {**SHOW, "remote_host": "https://cloud.example"}},
        {
            "/api/show": {
                **SHOW,
                "model_info": {"general.architecture": "fixture", "fixture.context_length": 4096},
            }
        },
        {
            "/api/show": {
                **SHOW,
                "model_info": {"general.architecture": "fixture", "fixture.context_length": True},
            }
        },
        {"/api/version": {"version": "credential-containing invalid version"}},
    ],
)
def test_unavailable_or_incompatible_artifact_closes_clients_without_inference(overrides):
    runtime = Runtime(overrides=overrides)

    async def scenario():
        model = runtime.model()
        with pytest.raises(ConversationModelError) as caught:
            async with model:
                pytest.fail("Unexpected prepared model")
        assert caught.value.code == "model_unavailable"
        assert model._http.is_closed
        assert model._model._client._client.is_closed

    asyncio.run(scenario())
    assert "/api/chat" not in [request.url.path for request in runtime.requests]


def test_input_token_counter_required_and_output_allowance_reserved_before_inference():
    async def scenario():
        runtime = Runtime()
        async with runtime.model(count_input_tokens=None) as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([])
            assert caught.value.code == "model_unavailable"
        assert len(runtime.requests) == 3
        for count, code in [
            (7168, None),
            (7169, "chat_limit_exceeded"),
            (True, "model_invalid_response"),
        ]:
            runtime = Runtime()
            runtime.tokens = count
            async with runtime.model() as model:
                if code:
                    with pytest.raises(ConversationModelError) as caught:
                        await model.generate([])
                    assert caught.value.code == code
                else:
                    await model.generate([])
            assert len(runtime.requests) == (3 if code else 4)

    asyncio.run(scenario())


@pytest.mark.parametrize("input_tokens,accepted", [(7680, True), (7681, False)])
def test_completion_schema_counts_toward_8192_tokens_with_512_reserved(input_tokens, accepted):
    runtime = Runtime(completion_response(REPLY))
    runtime.tokens = input_tokens

    async def scenario():
        async with runtime.model(settings(chat_max_output_tokens=512)) as model:
            if accepted:
                assert (await model.generate([])).reply.message == REPLY["message"]
            else:
                with pytest.raises(ConversationModelError) as caught:
                    await model.generate([])
                assert caught.value.code == "chat_limit_exceeded"

    asyncio.run(scenario())
    assert len(runtime.requests) == (4 if accepted else 3)
    assert len(runtime.token_requests) == 1
    assert len(runtime.token_requests[0]["tools"]) == 15
    assert runtime.token_requests[0]["tools"][-1]["function"]["name"] == "finish_conversation"


def test_utf8_context_includes_instructions_and_tools_at_exact_byte_boundary():
    async def scenario():
        runtime = Runtime()
        async with runtime.model() as model:
            messages = [{"role": "user", "content": ""}]
            size = len(
                serialized(
                    {
                        "messages": [{"role": "system", "content": REPLY_INSTRUCTIONS}, *messages],
                        "tools": model._tools,
                    }
                )
            )
            remaining = CONTEXT_BYTES - size
            messages[0]["content"] = "é" * (remaining // 2) + "x" * (remaining % 2)
            await model.generate(messages)
            messages[0]["content"] += "x"
            with pytest.raises(ConversationModelError) as caught:
                await model.generate(messages)
            assert caught.value.code == "chat_limit_exceeded"
        assert len(runtime.requests) == 4
        assert len(runtime.token_requests) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "exception,code",
    [
        (httpx.ReadTimeout("api_key=fixture-secret"), "chat_timeout"),
        (httpx.ConnectError("http://user:fixture-secret@localhost"), "model_unavailable"),
        (RuntimeError("api_key=fixture-secret"), "model_unavailable"),
    ],
)
def test_errors_are_fixed_and_no_automatic_retry_occurs(exception, code):
    runtime = Runtime(exception)

    async def scenario():
        async with runtime.model() as model:
            with pytest.raises(ConversationModelError) as caught:
                await model.generate([])
            assert caught.value.code == code
            assert "fixture-secret" not in str(caught.value)

    asyncio.run(scenario())
    assert len(runtime.requests) == 4


def test_absolute_timeout_and_cancellation_close_clients_without_retry():
    async def slow(_):
        await asyncio.sleep(60)
        pytest.fail("Inference was not cancelled")

    async def scenario():
        runtime = Runtime(overrides={"/api/chat": slow})
        model = runtime.model(settings(chat_model_timeout_seconds=0.02))
        with pytest.raises(ConversationModelError) as caught:
            async with model:
                await model.generate([])
        assert caught.value.code == "chat_timeout"
        assert model._http.is_closed
        assert len(runtime.requests) == 4
        runtime = Runtime(overrides={"/api/chat": slow})
        model = runtime.model()
        with pytest.raises(asyncio.CancelledError):
            async with model:
                task = asyncio.create_task(model.generate([]))
                await asyncio.sleep(0.01)
                task.cancel()
                await task
        assert model._http.is_closed
        assert len(runtime.requests) == 4

    asyncio.run(scenario())


def test_redirects_and_oversized_output_are_not_followed_or_accepted():
    async def redirect(_):
        return httpx.Response(307, headers={"location": "https://cloud.example/api/chat"})

    async def scenario():
        for runtime, code in [
            (Runtime(overrides={"/api/chat": redirect}), "model_unavailable"),
            (
                Runtime(
                    chat_response(message={"role": "assistant", "content": "x" * RECORD_BYTES})
                ),
                "model_invalid_response",
            ),
        ]:
            async with runtime.model() as model:
                with pytest.raises(ConversationModelError) as caught:
                    await model.generate([])
                assert caught.value.code == code
            assert len(runtime.requests) == 4
            assert all(request.url.host == "127.0.0.1" for request in runtime.requests)

    asyncio.run(scenario())


def test_debug_logging_is_rejected_before_prompt_can_be_printed():
    async def scenario():
        runtime = Runtime()
        async with runtime.model() as model:
            set_debug(True)
            try:
                with pytest.raises(ConversationModelError) as caught:
                    await model.generate([])
                assert caught.value.code == "model_unavailable"
            finally:
                set_debug(False)
        assert len(runtime.requests) == 3

    asyncio.run(scenario())


@pytest.mark.parametrize("native_completion", [False, True])
def test_known_keys_and_connection_passwords_are_redacted_before_inference_and_return(
    native_completion,
):
    secret = "fixture-configured-key"
    reply = chat_response(
        message={
            "role": "assistant",
            "content": json.dumps(
                {
                    "message": (
                        f"{secret} mongodb://user:database-secret@localhost Bearer fixture-token"
                    )
                }
            ),
        }
    )
    if native_completion:
        reply = completion_response(json.loads(reply["message"]["content"]))
    runtime = Runtime(reply)

    async def scenario():
        config = settings(
            project_api_keys={"demo": secret},
            mongodb_uri="mongodb://user:database-secret@localhost",
        )
        async with runtime.model(config) as model:
            result = await model.generate([{"role": "user", "content": secret}])
            assert secret not in json.dumps(result.model_dump())
            assert "database-secret" not in result.reply.message
            assert "fixture-token" not in result.reply.message
            assert "[REDACTED]" in result.reply.message

    asyncio.run(scenario())
    assert secret.encode() not in runtime.requests[-1].content


def test_streaming_decoded_byte_limit_includes_compressed_responses_and_closes_stream():
    class Chunks(httpx.AsyncByteStream):
        def __init__(self, chunks):
            self.chunks = chunks
            self.yielded = 0
            self.closed = False

        async def __aiter__(self):
            for chunk in self.chunks:
                self.yielded += 1
                yield chunk

        async def aclose(self):
            self.closed = True

    async def scenario():
        base = json.dumps(chat_response()).encode()
        exact = base + b" " * (RECORD_BYTES - len(base))
        for chunks, headers, accepted in [
            ([exact], {}, True),
            ([exact, b" ", b"must not be consumed"], {}, False),
            ([gzip.compress(exact + b" ")], {"content-encoding": "gzip"}, False),
        ]:
            stream = Chunks(chunks)

            async def response(_, headers=headers, stream=stream):
                return httpx.Response(200, headers=headers, stream=stream)

            runtime = Runtime(overrides={"/api/chat": response})
            async with runtime.model() as model:
                if accepted:
                    assert (await model.generate([])).reply.message == REPLY["message"]
                else:
                    with pytest.raises(ConversationModelError) as caught:
                        await model.generate([])
                    assert caught.value.code == "model_invalid_response"
            assert stream.closed
            assert stream.yielded == min(2, len(chunks))

    asyncio.run(scenario())


def test_preflight_errors_are_safe_and_close_clients():
    async def scenario():
        for error, code in [
            (httpx.ReadTimeout("password=fixture-secret"), "chat_timeout"),
            (RuntimeError("password=fixture-secret"), "model_unavailable"),
        ]:
            runtime = Runtime(overrides={"/api/tags": error})
            model = runtime.model()
            with pytest.raises(ConversationModelError) as caught:
                async with model:
                    pytest.fail("Unexpected prepared model")
            assert caught.value.code == code
            assert "fixture-secret" not in str(caught.value)
            assert model._http.is_closed
            assert model._model._client._client.is_closed
            assert len(runtime.requests) == 1

    asyncio.run(scenario())

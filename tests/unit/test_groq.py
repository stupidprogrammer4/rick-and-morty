import json

import httpx
import pytest
from pydantic import SecretStr

from src.config.settings import ModelCredentials, PortalAppSettings
from src.modules.automation.agents.domain.dtos import (
    AgentHistory,
    AgentMessage,
)
from src.modules.automation.agents.infra.groq import GroqClient


@pytest.mark.asyncio
@pytest.mark.parametrize("with_tools", [False, True])
async def test_groq_parameters_and_reported_cost(snapshot, with_tools):
    advertised = {
        "model",
        "messages",
        "max_tokens",
        "tools",
        "tool_choice",
        "reasoning_effort",
        "parallel_tool_calls",
    }

    def provider(request):
        payload = json.loads(request.content)
        assert set(payload) <= advertised
        assert request.url == "https://api.groq.com/openai/v1/chat/completions"
        assert "provider" not in payload
        if "tools" in payload:
            assert payload["tools"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "Ready 🧪"}}
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 10,
                    "cost": 0.000056,
                },
            },
        )

    runtime = PortalAppSettings.model_construct(
        ai=ModelCredentials(api_key=SecretStr("external-test-key"))
    )

    tools = (
        [
            {
                "type": "function",
                "function": {
                    "name": "read_article",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        if with_tools
        else []
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(provider)
    ) as client:
        llm = GroqClient(client, runtime, snapshot[0])
        result = await llm.complete(
            AgentHistory(messages=[AgentMessage(role="user", content="Hi")]),
            tools,
        )
    assert result.message.content == "Ready 🧪"
    assert result.cost_usd == "5.6e-05"
    assert result.input_tokens == 100


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_choice", ["required", "auto"])
async def test_groq_tool_reply_preserves_choice_and_reasoning(
    snapshot,
    tool_choice,
):
    configuration = snapshot[0].model_copy(
        update={
            "ai": snapshot[0].ai.model_copy(
                update={
                    "model": "external-free-test-model",
                    "reasoning_effort": "low",
                    "tool_choice": tool_choice,
                    "input_usd_per_million": 0,
                    "output_usd_per_million": 0,
                }
            )
        }
    )

    def provider(request):
        payload = json.loads(request.content)
        assert payload["reasoning_effort"] == "low"
        assert "provider" not in payload
        if tool_choice == "required":
            assert "tools" not in payload
            assert payload["response_format"]["json_schema"]["strict"]
        else:
            assert payload.get("tool_choice", "auto") == "auto"
            assert (
                payload["tools"][0]["function"]["name"] == "create_post_draft"
            )
        if tool_choice == "required":
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": '{"draft":{"title":"News"}}',
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "cost": 0,
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "free-news",
                                    "type": "function",
                                    "function": {
                                        "name": "create_post_draft",
                                        "arguments": json.dumps(
                                            {"draft": {"title": "News"}}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "cost": 0,
                },
            },
        )

    runtime = PortalAppSettings.model_construct(
        ai=ModelCredentials(api_key=SecretStr("external-test-key"))
    )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(provider)
    ) as client:
        reply = await GroqClient(client, runtime, configuration).complete(
            AgentHistory(
                messages=[AgentMessage(role="user", content="News")],
                tool_choice=tool_choice,
            ),
            [
                {
                    "type": "function",
                    "function": {
                        "name": "create_post_draft",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        )
    assert reply.message.tool_calls is not None
    assert reply.message.tool_calls[0].function.name == "create_post_draft"
    assert reply.cost_usd == "0"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [429, 502, "timeout", 404])
async def test_model_outages_are_retryable_without_exposing_provider_body(
    snapshot, failure
):
    from src.modules.automation.agents.domain.dtos import (
        ModelTemporarilyUnavailable,
    )

    runtime = PortalAppSettings.model_construct(
        ai=ModelCredentials(api_key=SecretStr("external-test-key"))
    )

    def provider(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private provider detail", request=request)
        return httpx.Response(
            failure, json={"error": "private provider detail"}
        )

    expected = (
        httpx.HTTPStatusError
        if failure == 404
        else ModelTemporarilyUnavailable
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(provider)
    ) as client:
        with pytest.raises(expected) as error:
            await GroqClient(client, runtime, snapshot[0]).complete(
                AgentHistory(
                    messages=[AgentMessage(role="user", content="Hi")]
                ),
                [],
            )
    assert "private provider detail" not in str(error.value)

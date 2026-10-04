import json

import httpx
import pytest
from pydantic import SecretStr

from src.config.settings import ModelCredentials
from src.modules.automation.agents.domain.dtos import (
    AgentHistory,
    AgentMessage,
)
from src.modules.automation.agents.infra.openrouter import OpenRouterClient


@pytest.mark.asyncio
@pytest.mark.parametrize("with_tools", [False, True])
async def test_provider_parameter_routing_and_paid_reply(snapshot, with_tools):
    # The live GPT-4.1 Mini endpoint advertises max_tokens and tools, but
    # not parallel_tool_calls. Parameter filtering rejects the whole request
    # if an unsupported option is present, even when its value is false.
    advertised = {"model", "messages", "provider", "max_tokens", "tools"}

    def provider(request):
        payload = json.loads(request.content)
        assert set(payload) <= advertised
        assert payload["provider"]["require_parameters"] is True
        assert payload["provider"]["data_collection"] == "deny"
        assert payload["provider"]["max_price"]["prompt"] == 0.4
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

    class Runtime:
        ai = ModelCredentials(api_key=SecretStr("external-test-key"))

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
        llm = OpenRouterClient(client, Runtime(), snapshot[0])
        result = await llm.complete(
            AgentHistory(messages=[AgentMessage(role="user", content="Hi")]),
            tools,
        )
    assert result.message.content == "Ready 🧪"
    assert result.cost_usd == "5.6e-05"
    assert result.input_tokens == 100

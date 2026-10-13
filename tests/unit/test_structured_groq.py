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
async def test_single_required_tool_uses_schema_and_retains_function_identity(
    snapshot,
):
    def reply(request):
        body = json.loads(request.content)
        assert "tools" not in body
        assert body["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"draft":{"evidence_ids":[71]}}',
                        }
                    }
                ],
                "usage": {"prompt_tokens": 4, "completion_tokens": 8},
            },
        )

    settings = PortalAppSettings.model_construct(
        ai=ModelCredentials(api_key=SecretStr("test"))
    )
    tool = {
        "type": "function",
        "function": {
            "name": "save_draft",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft": {
                        "type": "object",
                        "properties": {
                            "evidence_ids": {
                                "type": "array",
                                "items": {"type": "integer"},
                            }
                        },
                        "required": ["evidence_ids"],
                    }
                },
                "required": ["draft"],
            },
        },
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http:
        result = await GroqClient(http, settings, snapshot[0]).complete(
            AgentHistory(
                messages=[AgentMessage(role="user", content="Save the draft")],
                tool_choice="required",
            ),
            [tool],
        )
    assert result.message.tool_calls is not None
    assert len(result.message.tool_calls) == 1
    assert result.message.tool_calls[0].function.name == "save_draft"
    assert json.loads(result.message.tool_calls[0].function.arguments) == {
        "draft": {"evidence_ids": [71]}
    }

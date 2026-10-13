import os
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values
from pydantic import SecretStr

from src.config.settings import ModelCredentials, PortalAppSettings
from src.modules.automation.agents.domain.dtos import (
    AgentHistory,
    AgentMessage,
)
from src.modules.automation.agents.infra.groq import GroqClient


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("GROQ_LIVE") != "1", reason="Opt-in live Groq")
async def test_live_adapter_completes_tool_round_trip(snapshot):
    key = dotenv_values(Path(__file__).parents[2] / ".env")["GROQ_API_KEY"]
    assert key
    settings = PortalAppSettings.model_construct(
        ai=ModelCredentials(api_key=SecretStr(key))
    )
    messages = [
        AgentMessage(
            role="system",
            content=(
                "Call read_probe before answering. "
                "Use its returned value verbatim."
            ),
        ),
        AgentMessage(role="user", content="Call read_probe now."),
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_probe",
                "description": "Read the probe value",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    async with httpx.AsyncClient(timeout=45) as http:
        model = GroqClient(http, settings, snapshot[0])
        reply = await model.complete(
            AgentHistory(messages=messages, tool_choice="required"), tools
        )
        assert reply.message.tool_calls
        call = reply.message.tool_calls[0]
        assert call.function.name == "read_probe"
        messages.extend(
            [
                reply.message,
                AgentMessage(
                    role="tool",
                    tool_call_id=call.id,
                    content="GROQ_PROBE_731",
                ),
            ]
        )
        final = await model.complete(AgentHistory(messages=messages), [])
    assert "GROQ_PROBE_731" in (final.message.content or "")
    assert final.input_tokens > 0

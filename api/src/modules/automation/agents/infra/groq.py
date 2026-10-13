import json
from typing import Any
from uuid import uuid4

import httpx

from portal_contracts.configuration import PortalConfiguration
from src.config.settings import PortalAppSettings
from src.modules.automation.agents.domain.dtos import (
    AgentHistory,
    AgentMessage,
    LLMReply,
    ModelTemporarilyUnavailable,
    ToolCall,
    ToolFunction,
)
from src.modules.automation.agents.infra.schema import strict_schema


class GroqClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: PortalAppSettings,
        configuration: PortalConfiguration,
    ):
        self.client = client
        self.settings = configuration.ai
        self.api_key = settings.ai.api_key

    async def complete(
        self, history: AgentHistory, tools: list[dict[str, Any]]
    ) -> LLMReply:
        if (
            self.settings.mode != "groq"
            or not self.settings.model
            or not self.api_key.get_secret_value()
        ):
            raise ValueError("مدل Groq هنوز تنظیم نشده.")
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [
                message.model_dump(exclude_none=True)
                for message in history.messages
            ],
            "max_tokens": self.settings.max_output_tokens,
        }
        if self.settings.reasoning_effort is not None:
            payload["reasoning_effort"] = self.settings.reasoning_effort
        required_function = None
        if (
            history.tool_choice == "required"
            and self.settings.tool_choice == "required"
            and len(tools) == 1
        ):
            sole_tool = next(iter(tools))
            required_function = sole_tool["function"]
            payload["temperature"] = 0.2
            payload["messages"].append(
                {
                    "role": "system",
                    "content": (
                        "For this response, return only a JSON object of the "
                        "arguments for the supplied schema. The host executes "
                        "the declared function. Do not emit a tool call, "
                        "function "
                        "name, wrapper, Markdown or commentary."
                    ),
                }
            )
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "required_tool_arguments",
                    "strict": True,
                    "schema": strict_schema(required_function["parameters"]),
                },
            }
        if tools and required_function is None:
            payload["tools"] = tools
            payload["parallel_tool_calls"] = False
            if history.tool_choice == "required":
                payload["tool_choice"] = self.settings.tool_choice
        try:
            response = await self.client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": "Bearer "
                    + self.api_key.get_secret_value()
                },
                json=payload,
                timeout=60,
            )
        except httpx.TransportError as exc:
            raise ModelTemporarilyUnavailable(
                "Model connection temporarily unavailable"
            ) from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise ModelTemporarilyUnavailable(
                f"Model temporarily unavailable (HTTP {response.status_code})"
            )
        response.raise_for_status()
        payload = response.json()
        usage = payload["usage"]
        message = AgentMessage.model_validate(payload["choices"][0]["message"])
        if required_function is not None:
            arguments = message.content
            if arguments is None:
                raise ValueError("Structured tool arguments are missing")
            json.loads(arguments)
            message = AgentMessage(
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id="groq_" + uuid4().hex,
                        function=ToolFunction(
                            name=required_function["name"], arguments=arguments
                        ),
                    )
                ],
            )
        return LLMReply(
            message=message,
            input_tokens=usage["prompt_tokens"],
            output_tokens=usage["completion_tokens"],
            cost_usd=str(usage["cost"])
            if usage.get("cost") is not None
            else None,
        )

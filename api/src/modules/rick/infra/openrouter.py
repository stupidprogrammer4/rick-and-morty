from typing import Any

import httpx

from portal_contracts.configuration import PortalConfiguration
from src.config.settings import PortalAppSettings
from src.modules.rick.domain.dtos import AgentHistory, AgentMessage, LLMReply


class OpenRouterClient:
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
            self.settings.mode != "openrouter"
            or not self.settings.model
            or not self.api_key.get_secret_value()
        ):
            raise ValueError("مدل OpenRouter هنوز تنظیم نشده.")
        response = await self.client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": "Bearer " + self.api_key.get_secret_value()
            },
            json={
                "model": self.settings.model,
                "messages": [
                    message.model_dump(exclude_none=True)
                    for message in history.messages
                ],
                "tools": tools,
                "parallel_tool_calls": False,
                "max_tokens": self.settings.max_output_tokens,
                "provider": {
                    "require_parameters": True,
                    "data_collection": "allow"
                    if self.settings.allow_data_collection
                    else "deny",
                    "max_price": {
                        "prompt": float(
                            self.settings.input_usd_per_million or 0
                        ),
                        "completion": float(
                            self.settings.output_usd_per_million or 0
                        ),
                        "request": float(self.settings.maximum_request_usd),
                    },
                },
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        usage = payload["usage"]
        return LLMReply(
            message=AgentMessage.model_validate(
                payload["choices"][0]["message"]
            ),
            input_tokens=usage["prompt_tokens"],
            output_tokens=usage["completion_tokens"],
            cost_usd=str(usage["cost"])
            if usage.get("cost") is not None
            else None,
        )

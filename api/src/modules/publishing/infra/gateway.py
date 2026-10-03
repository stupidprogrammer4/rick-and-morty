import httpx

from portal_contracts.telegram import (
    DeliveryResult,
    ReactionRequest,
    TelegramDelivery,
    TypingRequest,
)
from src.config.settings import PortalAppSettings


class TelegramGateway:
    def __init__(self, client: httpx.AsyncClient, settings: PortalAppSettings):
        self.client = client
        self.settings = settings

    async def send(self, data: TelegramDelivery) -> DeliveryResult:
        try:
            response = await self.client.post(
                self.settings.portal.gateway_url + "/internal/messages",
                json=data.model_dump(mode="json"),
                headers={
                    "Authorization": "Bearer "
                    + self.settings.security.service_key.get_secret_value()
                },
                timeout=25,
            )
            response.raise_for_status()
            result = DeliveryResult.model_validate(response.json())
        except (httpx.HTTPError, ValueError):
            result = DeliveryResult(status="unknown", reason="gateway_unknown")
        return result

    async def react(self, data: ReactionRequest) -> None:
        response = await self.client.post(
            self.settings.portal.gateway_url + "/internal/reactions",
            json=data.model_dump(mode="json"),
            headers={
                "Authorization": "Bearer "
                + self.settings.security.service_key.get_secret_value()
            },
            timeout=5,
        )
        response.raise_for_status()

    async def typing(self, data: TypingRequest) -> None:
        response = await self.client.post(
            self.settings.portal.gateway_url + "/internal/typing",
            json=data.model_dump(mode="json"),
            headers={
                "Authorization": "Bearer "
                + self.settings.security.service_key.get_secret_value()
            },
            timeout=5,
        )
        response.raise_for_status()

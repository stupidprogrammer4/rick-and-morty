import httpx

from portal_contracts.media import MediaFileDelivery, MediaFileResult
from src.config.settings import PortalAppSettings


class MediaGateway:
    def __init__(self, client: httpx.AsyncClient, settings: PortalAppSettings):
        self.client = client
        self.settings = settings

    def headers(self) -> dict[str, str]:
        return {
            "Authorization": "Bearer "
            + self.settings.security.service_key.get_secret_value()
        }

    async def send(self, data: MediaFileDelivery) -> MediaFileResult:
        try:
            response = await self.client.post(
                self.settings.portal.gateway_url + "/internal/media/files",
                headers=self.headers(),
                json=data.model_dump(),
                timeout=300,
            )
            response.raise_for_status()
            result = MediaFileResult.model_validate(response.json())
        except (httpx.HTTPError, ValueError):
            result = MediaFileResult(
                status="unknown", reason="media_delivery_unknown"
            )
        return result

    async def notify(self, owner_id: int, text: str) -> None:
        try:
            await self.client.post(
                self.settings.portal.gateway_url
                + "/internal/media/notifications",
                headers=self.headers(),
                json={"owner_id": owner_id, "text": text},
                timeout=15,
            )
        except httpx.HTTPError:
            pass

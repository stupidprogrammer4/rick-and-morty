from typing import Any

import httpx

from portal_bots.config.settings import BotSettings


class BackendUnavailable(Exception):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class BackendClient:
    def __init__(self, client: httpx.AsyncClient, settings: BotSettings):
        self.client = client
        self.settings = settings

    async def request(
        self,
        method: str,
        path: str,
        owner_id: int,
        *,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        request_headers = {
            "Authorization": "Bearer "
            + self.settings.service_key.get_secret_value(),
            "X-Portal-Owner": str(owner_id),
            **(headers or {}),
        }
        try:
            response = await self.client.request(
                method,
                self.settings.api_url + "/internal" + path,
                headers=request_headers,
                json=data,
                timeout=6,
            )
        except httpx.HTTPError as exc:
            raise BackendUnavailable(
                "ارتباط با API برقرار نشد؛ دوباره بررسی کن.", retryable=True
            ) from exc
        payload = response.json()
        if response.status_code >= 400:
            error = payload.get("error") or {}
            detail = (
                error.get("message") or "درخواست معتبر نیست یا قابل اجرا نیست."
            )
            raise BackendUnavailable(detail)
        return payload["data"]

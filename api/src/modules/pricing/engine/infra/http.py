from urllib.parse import urlencode

import httpx

from src.shared.http import SourceHTTPClient


class PriceHTTPGateway:
    def __init__(
        self,
        client: SourceHTTPClient,
        headers: dict[str, str],
        timeout: float,
        allowed_hosts: set[str],
    ):
        self.client = client
        self.headers = headers
        self.timeout = timeout
        self.allowed_hosts = allowed_hosts

    async def request(
        self,
        url: str,
        *,
        method: str = "GET",
        params: dict | None = None,
        json: dict | None = None,
    ) -> httpx.Response:
        if params:
            url += ("&" if "?" in url else "?") + urlencode(params, doseq=True)
        try:
            content = await self.client.request(
                method,
                url,
                self.allowed_hosts,
                headers=self.headers,
                json=json,
                timeout=self.timeout,
            )
        except ValueError as exc:
            if str(exc).startswith("Source returned HTTP "):
                status = int(str(exc).rsplit(" ", 1)[-1])
                response = httpx.Response(
                    status, request=httpx.Request(method, url)
                )
                raise httpx.HTTPStatusError(
                    "Price source request refused",
                    request=response.request,
                    response=response,
                ) from None
            raise
        return httpx.Response(
            200, content=content, request=httpx.Request(method, url)
        )

    async def get(
        self, url: str, *, params: dict | None = None
    ) -> httpx.Response:
        result = await self.request(url, params=params)
        return result

    async def post(self, url: str, *, json: dict) -> httpx.Response:
        result = await self.request(url, method="POST", json=json)
        return result

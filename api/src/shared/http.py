import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

import aiohttp
from aiohttp.abc import ResolveResult


class PublicResolver(aiohttp.ThreadedResolver):
    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: socket.AddressFamily = socket.AF_INET,
    ) -> list[ResolveResult]:
        records = await super().resolve(host, port, family)
        if not records or any(
            not ipaddress.ip_address(record["host"]).is_global
            for record in records
        ):
            raise ValueError("Source resolves to a non-public address")
        return records


class SourceHTTPClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def get(
        self,
        url: str,
        allowed_hosts: set[str],
        *,
        token: str = "",
        maximum_bytes: int = 1_000_000,
    ) -> bytes:
        data = await self.request(
            "GET",
            url,
            allowed_hosts,
            headers={"Authorization": "Bearer " + token} if token else {},
            maximum_bytes=maximum_bytes,
        )
        return data

    async def request(
        self,
        method: str,
        url: str,
        allowed_hosts: set[str],
        *,
        headers: dict[str, str] | None = None,
        json: dict | None = None,
        maximum_bytes: int = 1_000_000,
        timeout: float = 20,
    ) -> bytes:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in allowed_hosts
            or parsed.username
            or parsed.password
            or parsed.port not in {None, 443}
        ):
            raise ValueError("Only configured HTTPS source hosts are allowed")
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Non-public source address")
        if method not in {"GET", "POST"}:
            raise ValueError("Unsupported source method")
        async with self.session.request(
            method,
            url,
            headers=headers,
            json=json,
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            if response.status != 200:
                raise ValueError(f"Source returned HTTP {response.status}")
            if (
                response.content_length is not None
                and response.content_length > maximum_bytes
            ):
                raise ValueError("Source response is too large")
            try:
                data = await response.content.readexactly(maximum_bytes + 1)
            except asyncio.IncompleteReadError as exc:
                data = exc.partial
            if len(data) > maximum_bytes:
                raise ValueError("Source response is too large")
            return data

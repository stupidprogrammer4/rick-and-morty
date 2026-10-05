import asyncio
import ipaddress
import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http.cookiejar import MozillaCookieJar
from types import SimpleNamespace
from typing import Any
from urllib.parse import urljoin, urlsplit

import aiohttp
import certifi
from yarl import URL

from src.modules.media.sources.domain.dtos import DownloadProcessRequest
from src.modules.media.sources.infra.downloaders.network import public_address
from src.shared.http import PublicResolver


class MediaHTTP:
    def __init__(self, request: DownloadProcessRequest):
        self.request = request

    @staticmethod
    def validate(url: str) -> None:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in {None, 443}
        ):
            raise ValueError("Only public HTTPS media URLs are supported")
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            address = None
        if address is not None and not public_address(str(address)):
            raise ValueError("Private network destinations are blocked")

    async def redirect(
        self,
        session: aiohttp.ClientSession,
        context: SimpleNamespace,
        params: aiohttp.TraceRequestRedirectParams,
    ) -> None:
        location = params.response.headers.get("Location", "")
        self.validate(urljoin(str(params.url), location))

    @asynccontextmanager
    async def session(self) -> AsyncIterator[aiohttp.ClientSession]:
        trace = aiohttp.TraceConfig()
        trace.on_request_redirect.append(self.redirect)
        connector = aiohttp.TCPConnector(
            limit=self.request.policy.concurrent_downloads,
            resolver=PublicResolver(),
            ssl=ssl.create_default_context(cafile=certifi.where()),
        )
        async with aiohttp.ClientSession(
            connector=connector,
            trace_configs=[trace],
            trust_env=False,
            headers={"User-Agent": self.request.policy.http_user_agent},
            timeout=aiohttp.ClientTimeout(
                total=self.request.policy.item_timeout_seconds,
                sock_connect=self.request.policy.source_timeout_seconds,
                sock_read=self.request.policy.source_timeout_seconds,
            ),
        ) as session:
            if self.request.cookie_file:
                jar = MozillaCookieJar(self.request.cookie_file)
                jar.load()
                for cookie in jar:
                    session.cookie_jar.update_cookies(
                        {cookie.name: cookie.value or ""},
                        response_url=URL(
                            "https://"
                            + cookie.domain.lstrip(".")
                            + cookie.path
                        ),
                    )
            yield session

    async def metadata(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> bytes:
        self.validate(url)
        async with session.request(
            method, url, max_redirects=6, **kwargs
        ) as response:
            if response.status != 200:
                raise ValueError(
                    f"Media source returned HTTP {response.status}"
                )
            maximum = 4_000_000
            if (
                response.content_length is not None
                and response.content_length > maximum
            ):
                raise ValueError("Media metadata exceeds the size limit")
            try:
                data = await response.content.readexactly(maximum + 1)
            except asyncio.IncompleteReadError as exc:
                data = exc.partial
            if len(data) > maximum:
                raise ValueError("Media metadata exceeds the size limit")
            return data


class MediaBodyReader:
    def __init__(self, stream: aiohttp.StreamReader, maximum: int):
        self.stream = stream
        self.maximum = maximum
        self.received = 0

    async def read(self, size: int = -1) -> bytes:
        chunk = await self.stream.read(size)
        self.received += len(chunk)
        if self.received > self.maximum:
            raise ValueError("Media exceeds the Telegram file limit")
        return chunk

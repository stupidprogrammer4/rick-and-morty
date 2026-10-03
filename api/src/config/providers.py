from collections.abc import AsyncIterator

import aiohttp
import httpx
from dishka import Provider, Scope, alias, provide
from papilio.core.bootstrap import Bootstrapper
from papilio.core.config import Settings
from papilio.providers.base import CoreProvider
from papilio.providers.db import MySQLProvider

from src.config.settings import PortalAppSettings
from src.shared.http import PublicResolver, SourceHTTPClient


class RuntimeProvider(Provider):
    app_settings = alias(Settings, provides=PortalAppSettings)

    @provide(scope=Scope.APP)
    async def http(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(
            timeout=20, follow_redirects=False, trust_env=False
        ) as client:
            yield client

    @provide(scope=Scope.APP)
    async def sources(self) -> AsyncIterator[SourceHTTPClient]:
        connector = aiohttp.TCPConnector(
            resolver=PublicResolver(), limit=10, ttl_dns_cache=0
        )
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=20),
            headers={"User-Agent": "PapilioPortal/0.1"},
        ) as session:
            yield SourceHTTPClient(session)


def infrastructure_providers(settings: PortalAppSettings):
    if settings.db is None:
        raise ValueError("MySQL configuration required")
    return [MySQLProvider(settings.db), RuntimeProvider()]


def task_providers(settings: PortalAppSettings):
    return [
        CoreProvider(settings),
        *infrastructure_providers(settings),
        *Bootstrapper(settings.app.modules).boot_providers(),
    ]

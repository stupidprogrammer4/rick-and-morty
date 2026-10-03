from collections.abc import AsyncIterator

import aiohttp
import httpx
from dishka import Provider, Scope, alias, provide
from papilio.core.bootstrap import Bootstrapper
from papilio.core.config import RedisConfig, Settings
from papilio.providers.base import CoreProvider
from papilio.providers.db import MySQLProvider
from papilio.providers.redis import RedisProvider
from papilio_tasks.apps.schedulers.redis import SchedulerApplication
from taskiq import ScheduleSource

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


class SchedulerProvider(Provider):
    @provide(scope=Scope.APP)
    def scheduler(self) -> SchedulerApplication:
        from src.apps.scheduler import app

        return app

    @provide(scope=Scope.APP)
    def schedule_source(self, app: SchedulerApplication) -> ScheduleSource:
        return app.source.native


def infrastructure_providers(settings: PortalAppSettings):
    if settings.db is None:
        raise ValueError("MySQL configuration required")
    return [
        MySQLProvider(settings.db),
        RedisProvider(
            RedisConfig(
                url=settings.tasks.url,
                max_connections=10,
                socket_timeout=10,
                socket_connect_timeout=5,
                health_check_interval=30,
            )
        ),
        SchedulerProvider(),
        RuntimeProvider(),
    ]


def task_providers(settings: PortalAppSettings):
    return [
        CoreProvider(settings),
        *infrastructure_providers(settings),
        *Bootstrapper(settings.app.modules).boot_providers(),
    ]

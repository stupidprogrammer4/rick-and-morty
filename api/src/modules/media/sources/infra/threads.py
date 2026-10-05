import asyncio
from collections.abc import Callable
from functools import partial
from typing import ParamSpec, TypeVar

from anyio import CapacityLimiter, to_thread

from src.config.settings import PortalAppSettings

P = ParamSpec("P")
T = TypeVar("T")


class MediaMetadataThreads:
    def __init__(self, settings: PortalAppSettings):
        self.limiter = CapacityLimiter(settings.media.metadata_threads)

    async def run(
        self, operation: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> T:
        task = asyncio.create_task(
            to_thread.run_sync(
                partial(operation, *args, **kwargs), limiter=self.limiter
            )
        )
        try:
            result = await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            finally:
                raise
        return result

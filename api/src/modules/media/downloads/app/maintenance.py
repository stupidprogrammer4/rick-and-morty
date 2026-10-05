import time

from papilio.infra.db.transaction import transaction

from portal_contracts.media import MediaPolicy
from src.modules.media.downloads.infra.readers import MediaReader
from src.modules.media.downloads.interfaces import (
    IMediaItemService,
    IMediaJobService,
    IMediaQueue,
)
from src.modules.media.library.interfaces import IMediaAssetService
from src.modules.media.storage.infra.files import MediaFiles
from src.modules.ops.guards.interfaces import IPortalGuard
from src.shared.dates import utc_now


class MediaMaintenance:
    def __init__(
        self,
        jobs: IMediaJobService,
        items: IMediaItemService,
        reader: MediaReader,
        files: MediaFiles,
        policy: MediaPolicy,
        queue: IMediaQueue,
        guard: IPortalGuard,
        assets: IMediaAssetService,
    ):
        self.jobs = jobs
        self.items = items
        self.reader = reader
        self.files = files
        self.policy = policy
        self.queue = queue
        self.guard = guard
        self.assets = assets

    async def recover(self) -> None:
        async with transaction():
            await self.guard.lock("media-dispatch")
            rows = await self.jobs.expired(utc_now())
            ids = [row.id for row in rows]
            await self.items.interrupt_many(ids)
            await self.jobs.requeue_many(ids)
            await self.items.recover(utc_now())
        await self.queue.dispatch()

    async def clean(self) -> None:
        async with transaction():
            active = await self.reader.active_ids()
            await self.assets.prune()
        await self.files.clean(
            active, time.time() - self.policy.orphan_age_seconds
        )

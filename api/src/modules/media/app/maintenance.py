import asyncio
import time
from datetime import timedelta

from papilio.infra.db.transaction import transaction

from portal_contracts.media import MediaPolicy
from src.modules.media.infra.files import MediaFiles
from src.modules.media.infra.readers import MediaReader
from src.modules.media.interfaces import IMediaItemService, IMediaJobService
from src.shared.dates import utc_now


class MediaMaintenance:
    def __init__(
        self,
        jobs: IMediaJobService,
        items: IMediaItemService,
        reader: MediaReader,
        files: MediaFiles,
        policy: MediaPolicy,
    ):
        self.jobs = jobs
        self.items = items
        self.reader = reader
        self.files = files
        self.policy = policy

    async def recover(self) -> None:
        from src.media_tasks.schedulers import ExecuteMedia

        async with transaction():
            rows = await self.jobs.expired(utc_now())
            ids = [row.id for row in rows]
            await self.items.interrupt_many(ids)
            await self.jobs.requeue_many(ids)
            pending = await self.jobs.due(self.policy.active_global)
            pending_ids = [row.id for row in pending]
            await self.jobs.dispatch_many(
                pending_ids,
                utc_now()
                + timedelta(seconds=self.policy.item_timeout_seconds + 420),
            )
        await asyncio.gather(
            *(ExecuteMedia.enqueue(job_id=id) for id in pending_ids)
        )

    async def clean(self) -> None:
        async with transaction():
            active = await self.reader.active_ids()
        await self.files.clean(
            active, time.time() - self.policy.orphan_age_seconds
        )

import asyncio
import logging
from collections.abc import Sequence
from datetime import timedelta
from time import monotonic

from papilio.infra.db.transaction import transaction

from portal_contracts.media import MediaPolicy
from src.modules.media.domain.dtos import (
    MediaDownloadOutcome,
    MediaItemChange,
)
from src.modules.media.infra.files import MediaFiles
from src.modules.media.infra.readers import MediaReader
from src.modules.media.interfaces import (
    IMediaDownloader,
    IMediaItemService,
    IMediaJobService,
    IMediaQueue,
    IMediaWorkspace,
)
from src.modules.ops.interfaces import IPortalGuard
from src.shared.dates import utc_now

logger = logging.getLogger(__name__)


class MediaTransferBatch:
    def __init__(
        self,
        jobs: IMediaJobService,
        items: IMediaItemService,
        reader: MediaReader,
        downloader: IMediaDownloader,
        workspace: IMediaWorkspace,
        files: MediaFiles,
        queue: IMediaQueue,
        policy: MediaPolicy,
        guard: IPortalGuard,
    ):
        self.jobs = jobs
        self.items = items
        self.reader = reader
        self.downloader = downloader
        self.workspace = workspace
        self.files = files
        self.queue = queue
        self.policy = policy
        self.guard = guard

    async def execute(self, item_ids: Sequence[int]) -> None:
        async with transaction():
            await self.guard.lock("media-dispatch")
            records = await self.reader.transfers(item_ids)
            reserved = [
                data for data in records if data.item.status == "reserved"
            ]
            inputs = [
                data for data in reserved if data.job.status != "cancelled"
            ]
            lease = utc_now().replace(microsecond=0) + timedelta(
                seconds=self.policy.item_timeout_seconds + 420
            )
            changes = [
                data.item.model_copy(
                    update=MediaItemChange(
                        status="cancelled"
                        if data.job.status == "cancelled"
                        else "downloading",
                        lease_until=None
                        if data.job.status == "cancelled"
                        else lease,
                    ).model_dump(exclude_unset=True)
                )
                for data in reserved
            ]
            await self.items.save_many(changes)
            claimed = {row.id: row for row in changes}
            inputs = [
                data.model_copy(update={"item": claimed[data.item.id]})
                for data in inputs
            ]
            job_ids = sorted({data.job.id for data in inputs})
            await self.jobs.start_many(job_ids)
        if not inputs:
            await self.queue.dispatch()
            return
        published: set[int] = set()

        async def completed(data: MediaDownloadOutcome) -> None:
            await self.queue.downloaded(data)
            published.add(data.item_id)

        started = monotonic()
        try:
            try:
                await self.workspace.prepare_many(inputs)
                await self.downloader.download_many(inputs, completed)
            except Exception as exc:
                errors = [
                    MediaDownloadOutcome(
                        item_id=data.item.id,
                        job_id=data.job.id,
                        lease_until=data.item.lease_until,
                        error=type(exc).__name__ + ": " + str(exc)[:350],
                    )
                    for data in inputs
                    if data.item.id not in published
                ]
                await asyncio.gather(*(completed(error) for error in errors))
            logger.info(
                "media_download_batch items=%s seconds=%.3f",
                len(inputs),
                monotonic() - started,
            )
        finally:
            await self.files.remove_many(
                [data for data in inputs if data.item.id not in published]
            )
            await self.queue.complete_many(job_ids)
            await self.queue.dispatch()

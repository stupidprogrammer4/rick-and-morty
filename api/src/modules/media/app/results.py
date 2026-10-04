from papilio.infra.db.transaction import transaction

from src.modules.media.domain.dtos import MediaDownloadOutcome, MediaItemChange
from src.modules.media.infra.files import MediaFiles
from src.modules.media.interfaces import (
    IMediaCompletion,
    IMediaItemService,
    IMediaJobService,
    IMediaQueue,
)
from src.modules.ops.interfaces import IPortalGuard
from src.shared.dates import as_utc


class MediaDownloadRecorder:
    def __init__(
        self,
        jobs: IMediaJobService,
        items: IMediaItemService,
        files: MediaFiles,
        completion: IMediaCompletion,
        queue: IMediaQueue,
        guard: IPortalGuard,
    ):
        self.jobs = jobs
        self.items = items
        self.files = files
        self.completion = completion
        self.queue = queue
        self.guard = guard

    async def record(self, data: MediaDownloadOutcome) -> None:
        async with transaction():
            await self.guard.lock("media-dispatch")
            job = await self.jobs.record(data.job_id, lock=True)
            item = await self.items.get(data.item_id, lock=True)
            if item.job_id != job.id or item.status != "downloading":
                return
            if (
                data.lease_until is None
                or item.lease_until is None
                or as_utc(data.lease_until) != as_utc(item.lease_until)
            ):
                return
            downloaded = data.downloaded
            status = (
                "cancelled"
                if job.status == "cancelled"
                else "ready"
                if downloaded
                else "failed"
            )
            await self.items.change(
                item.id,
                MediaItemChange(
                    status=status,
                    lease_until=None,
                    error=data.error,
                    filename=downloaded.filename if downloaded else None,
                    downloaded_payload=downloaded.model_dump_json()
                    if downloaded
                    else None,
                    source_url=downloaded.source_url
                    if downloaded
                    else item.source_url,
                ),
            )
        if status != "ready":
            await self.files.remove_item(job.id, item.id)
        await self.completion.refresh(job.id)
        await self.queue.dispatch()

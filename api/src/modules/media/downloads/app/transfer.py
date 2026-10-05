import logging
from datetime import timedelta
from time import monotonic

from papilio.infra.db.transaction import transaction

from portal_contracts.media import MediaPolicy
from src.modules.media.downloads.domain.dtos import (
    MediaItemChange,
    MediaJobChange,
)
from src.modules.media.downloads.interfaces import (
    IMediaCompletion,
    IMediaItemService,
    IMediaJobService,
    IMediaQueue,
)
from src.modules.media.sources.domain.dtos import DownloadItem, SourceJob
from src.modules.media.sources.interfaces import IMediaFileDownloads
from src.modules.media.storage.infra.files import MediaFiles
from src.modules.media.storage.interfaces import IMediaWorkspace
from src.modules.ops.guards.interfaces import IPortalGuard
from src.shared.dates import utc_now

logger = logging.getLogger(__name__)


class MediaTransfer:
    def __init__(
        self,
        jobs: IMediaJobService,
        items: IMediaItemService,
        downloader: IMediaFileDownloads,
        completion: IMediaCompletion,
        files: MediaFiles,
        workspace: IMediaWorkspace,
        policy: MediaPolicy,
        queue: IMediaQueue,
        guard: IPortalGuard,
    ):
        self.jobs = jobs
        self.items = items
        self.downloader = downloader
        self.completion = completion
        self.files = files
        self.workspace = workspace
        self.policy = policy
        self.queue = queue
        self.guard = guard

    async def execute(self, item_id: int) -> None:
        async with transaction():
            await self.guard.lock("media-dispatch")
            parent = await self.items.get(item_id)
            row = await self.jobs.record(parent.job_id, lock=True)
            item = await self.items.get(item_id, lock=True)
            if item.status != "reserved":
                return
            job = row.model_copy()
            item = item.model_copy()
            cancelled = row.status == "cancelled"
            if cancelled:
                await self.items.change(
                    item_id,
                    MediaItemChange(status="cancelled", lease_until=None),
                )
            else:
                await self.jobs.change(
                    job.id, MediaJobChange(status="running", lease_until=None)
                )
                await self.items.change(
                    item_id,
                    MediaItemChange(
                        status="downloading",
                        lease_until=utc_now()
                        + timedelta(
                            seconds=self.policy.item_timeout_seconds + 420
                        ),
                    ),
                )
        if cancelled:
            await self.queue.dispatch()
            return
        started = monotonic()
        keep = False
        try:
            try:
                await self.workspace.prepare_item(job.id, item.id)
                downloaded = await self.downloader.download(
                    SourceJob.model_validate(job, from_attributes=True),
                    item.id,
                    DownloadItem.model_validate_json(item.payload),
                )
            except Exception as exc:
                logger.info(
                    "media_download job=%s item=%s status=failed seconds=%.3f",
                    job.id,
                    item.id,
                    monotonic() - started,
                )
                async with transaction():
                    await self.items.change(
                        item.id,
                        MediaItemChange(
                            status="failed",
                            lease_until=None,
                            error=type(exc).__name__ + ": " + str(exc)[:350],
                        ),
                    )
            else:
                logger.info(
                    "media_download job=%s item=%s seconds=%.3f",
                    job.id,
                    item.id,
                    monotonic() - started,
                )
                async with transaction():
                    current = await self.jobs.record(job.id, lock=True)
                    keep = current.status != "cancelled"
                    await self.items.change(
                        item.id,
                        MediaItemChange(
                            status="ready" if keep else "cancelled",
                            lease_until=None,
                            filename=downloaded.filename,
                            source_url=downloaded.source_url,
                            downloaded_payload=downloaded.model_dump_json(),
                        ),
                    )
        finally:
            if not keep:
                await self.files.remove_item(job.id, item.id)
            await self.completion.refresh(job.id)
            await self.queue.dispatch()

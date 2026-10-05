import logging
from datetime import timedelta
from time import monotonic

from papilio.infra.db.transaction import transaction

from portal_contracts.media import MediaFileDelivery
from src.modules.media.delivery.app.renderer import MediaCaptionRenderer
from src.modules.media.delivery.domain.dtos import MediaCaption
from src.modules.media.delivery.interfaces import IMediaGateway
from src.modules.media.downloads.domain.dtos import MediaItemChange
from src.modules.media.downloads.interfaces import (
    IMediaCompletion,
    IMediaItemService,
    IMediaJobService,
    IMediaQueue,
)
from src.modules.media.library.interfaces import IMediaAssetService
from src.modules.media.sources.domain.dtos import DownloadedFile
from src.modules.media.storage.infra.files import MediaFiles
from src.modules.ops.guards.interfaces import IPortalGuard
from src.shared.dates import as_utc, utc_now

logger = logging.getLogger(__name__)


class MediaDelivery:
    def __init__(
        self,
        jobs: IMediaJobService,
        items: IMediaItemService,
        gateway: IMediaGateway,
        files: MediaFiles,
        completion: IMediaCompletion,
        queue: IMediaQueue,
        guard: IPortalGuard,
        captions: MediaCaptionRenderer,
        assets: IMediaAssetService,
    ):
        self.jobs = jobs
        self.items = items
        self.gateway = gateway
        self.files = files
        self.completion = completion
        self.queue = queue
        self.guard = guard
        self.captions = captions
        self.assets = assets

    async def execute(self, job_id: int) -> None:
        async with transaction():
            await self.guard.lock("media-dispatch")
            row = await self.jobs.record(job_id, lock=True)
            cancelled = row.status == "cancelled"
            item = (
                await self.items.ready(job_id)
                if cancelled
                else await self.items.next_delivery(job_id)
            )
            if item is None or item.status != "ready":
                return
            if (
                item.available_at is not None
                and as_utc(item.available_at) > utc_now()
            ):
                return
            job = row.model_copy()
            item = item.model_copy()
            await self.items.change(
                item.id,
                MediaItemChange(
                    status="cancelled" if cancelled else "sending",
                    lease_until=None
                    if cancelled
                    else utc_now() + timedelta(seconds=360),
                ),
            )
        keep = False
        retry_at = None
        try:
            if cancelled:
                return
            downloaded = DownloadedFile.model_validate_json(
                item.downloaded_payload or ""
            )
            caption = self.captions.render(
                MediaCaption(
                    job_id=job.id,
                    position=item.position,
                    total=job.total,
                    title=downloaded.title,
                    source_url=downloaded.source_url,
                    provider=job.provider,
                )
            )
            started = monotonic()
            result = await self.gateway.send(
                MediaFileDelivery(
                    job_id=job.id,
                    item_id=item.id,
                    owner_id=job.owner_id,
                    filename=downloaded.filename,
                    kind=downloaded.kind,
                    caption=caption,
                    title=downloaded.title[:200],
                    performer=(downloaded.performer or "")[:200] or None,
                    file_id=downloaded.file_id,
                )
            )
            logger.info(
                "media_send job=%s item=%s status=%s seconds=%.3f",
                job.id,
                item.id,
                result.status,
                monotonic() - started,
            )
            keep = result.status == "rate_limited"
            retry_at = (
                utc_now() + timedelta(seconds=(result.retry_after or 5) + 1)
                if keep
                else None
            )
            async with transaction():
                if result.status == "cache_miss":
                    if downloaded.cache_key:
                        await self.assets.invalidate(downloaded.cache_key)
                    await self.items.change(
                        item.id,
                        MediaItemChange(
                            status="queued",
                            file_id=None,
                            filename=None,
                            downloaded_payload=None,
                            error=None,
                            lease_until=None,
                            available_at=None,
                        ),
                    )
                    return
                await self.items.change(
                    item.id,
                    MediaItemChange(
                        status="ready" if keep else result.status,
                        message_id=result.message_id,
                        file_id=result.file_id,
                        error=result.reason,
                        lease_until=None,
                        available_at=retry_at,
                    ),
                )
                if result.status == "sent" and result.file_id:
                    await self.assets.store(
                        job.bot_id,
                        downloaded.model_copy(
                            update={"file_id": result.file_id}
                        ),
                    )
            if retry_at is not None:
                await self.queue.dispatch_at(retry_at)
        finally:
            if not keep:
                await self.files.remove_item(job.id, item.id)
            await self.completion.refresh(job.id)
            await self.queue.dispatch()

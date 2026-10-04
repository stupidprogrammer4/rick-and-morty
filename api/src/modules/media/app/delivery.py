import logging
from datetime import timedelta
from html import escape
from time import monotonic

from papilio.infra.db.transaction import transaction

from portal_contracts.media import MediaFileDelivery
from src.modules.media.domain.dtos import DownloadedFile, MediaItemChange
from src.modules.media.infra.files import MediaFiles
from src.modules.media.interfaces import (
    IMediaCompletion,
    IMediaGateway,
    IMediaItemService,
    IMediaJobService,
    IMediaQueue,
)
from src.modules.ops.interfaces import IPortalGuard
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
    ):
        self.jobs = jobs
        self.items = items
        self.gateway = gateway
        self.files = files
        self.completion = completion
        self.queue = queue
        self.guard = guard

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
            source = escape(downloaded.source_url, quote=True)
            caption = (
                f"🦋 <b>{escape(downloaded.title[:150])}</b>\n"
                f"📦 {item.position} / {job.total} · #{job.id}\n"
                f'🔗 <a href="{source}">منبع فایل</a>'
            )
            if job.provider == "spotify":
                caption += (
                    "\n🎵 تطبیق با Spotify؛ فایل از منبع لینک‌شده تهیه شده است."
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
            if retry_at is not None:
                await self.queue.dispatch_at(retry_at)
        finally:
            if not keep:
                await self.files.remove_item(job.id, item.id)
            await self.completion.refresh(job.id)
            await self.queue.dispatch()

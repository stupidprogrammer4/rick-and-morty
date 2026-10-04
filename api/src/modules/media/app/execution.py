from datetime import timedelta
from html import escape

from papilio.infra.db.transaction import transaction

from portal_contracts.media import MediaFileDelivery, MediaPolicy
from src.modules.media.domain.dtos import (
    DownloadItem,
    MediaItemChange,
    MediaJobChange,
)
from src.modules.media.domain.models import MediaJobModel
from src.modules.media.infra.files import MediaFiles
from src.modules.media.infra.readers import MediaReader
from src.modules.media.interfaces import (
    IMediaDownloader,
    IMediaGateway,
    IMediaItemService,
    IMediaJobService,
    IMediaWorkspace,
)
from src.shared.dates import as_utc, utc_now


class MediaExecutor:
    def __init__(
        self,
        jobs: IMediaJobService,
        items: IMediaItemService,
        reader: MediaReader,
        downloader: IMediaDownloader,
        files: MediaFiles,
        gateway: IMediaGateway,
        policy: MediaPolicy,
        workspace: IMediaWorkspace,
    ):
        self.jobs = jobs
        self.items = items
        self.reader = reader
        self.downloader = downloader
        self.files = files
        self.gateway = gateway
        self.policy = policy
        self.workspace = workspace

    async def execute(self, job_id: int) -> None:
        async with transaction():
            row = await self.jobs.record(job_id, lock=True)
            if row.status != "queued":
                return
            if (
                row.available_at is not None
                and as_utc(row.available_at) > utc_now()
            ):
                return
            if not self.policy.enabled:
                return
            job = row.model_copy()
            await self.jobs.change(
                job_id,
                MediaJobChange(
                    status="planning" if job.total == 0 else "running",
                    lease_until=utc_now()
                    + timedelta(
                        seconds=self.policy.item_timeout_seconds + 420
                    ),
                ),
            )
        try:
            if job.total == 0:
                await self.plan(job)
            else:
                await self.deliver_next(job)
        except Exception as exc:
            async with transaction():
                current = await self.jobs.record(job_id, lock=True)
                if current.status != "cancelled":
                    await self.jobs.change(
                        job_id,
                        MediaJobChange(
                            status="failed",
                            error=type(exc).__name__ + ": " + str(exc)[:350],
                        ),
                    )
            await self.gateway.notify(
                job.owner_id,
                f"⚠️ درخواست <b>#{job_id}</b> انجام نشد.\n"
                "ممکن است لینک نیازمند ورود باشد، منبع پاسخ ندهد "
                "یا سقف حجم/زمان دانلود پر شده باشد.\n"
                f"📋 جزئیات: /status {job_id}",
            )
        finally:
            await self.files.remove(job_id)

    async def plan(self, job: MediaJobModel) -> None:
        await self.workspace.prepare(job.id)
        plan = await self.downloader.plan(job)
        if not plan.items or len(plan.items) > self.policy.max_playlist_items:
            raise ValueError("Empty or oversized media collection")
        async with transaction():
            current = await self.jobs.record(job.id, lock=True)
            if current.status == "cancelled":
                return
            await self.items.create_many(job.id, plan)
            await self.jobs.change(
                job.id,
                MediaJobChange(
                    status="queued", total=len(plan.items), lease_until=None
                ),
            )
        await self.gateway.notify(
            job.owner_id,
            f"📦 <b>#{job.id}</b> · {len(plan.items)} فایل شناسایی شد\n"
            "🚀 دانلود و ارسال تدریجی شروع می‌شود.\n"
            f"🛑 /cancel {job.id}",
        )

    async def deliver_next(self, job: MediaJobModel) -> None:
        async with transaction():
            item = await self.items.next(job.id)
            if item is not None:
                item = item.model_copy()
                await self.items.change(
                    item.id, MediaItemChange(status="downloading")
                )
        if item is None:
            await self.finish(job)
            return
        try:
            await self.workspace.prepare(job.id)
            downloaded = await self.downloader.download(
                job, DownloadItem.model_validate_json(item.payload)
            )
        except Exception as exc:
            async with transaction():
                await self.items.change(
                    item.id,
                    MediaItemChange(
                        status="failed",
                        error=type(exc).__name__ + ": " + str(exc)[:350],
                    ),
                )
                current = await self.jobs.record(job.id, lock=True)
                if current.status != "cancelled":
                    await self.jobs.change(
                        job.id,
                        MediaJobChange(status="queued", lease_until=None),
                    )
            return
        async with transaction():
            current = await self.jobs.record(job.id, lock=True)
            if current.status == "cancelled":
                await self.items.change(
                    item.id, MediaItemChange(status="cancelled")
                )
                return
            await self.items.change(
                item.id,
                MediaItemChange(
                    status="sending",
                    filename=downloaded.filename,
                    source_url=downloaded.source_url,
                ),
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
        async with transaction():
            await self.items.change(
                item.id,
                MediaItemChange(
                    status="queued"
                    if result.status == "rate_limited"
                    else result.status,
                    message_id=result.message_id,
                    file_id=result.file_id,
                    error=result.reason,
                ),
            )
            current = await self.jobs.record(job.id, lock=True)
            counts = await self.reader.counts(job.id)
            await self.jobs.change(
                job.id,
                MediaJobChange(
                    status="cancelled"
                    if current.status == "cancelled"
                    else "queued",
                    sent=counts.sent,
                    failed=counts.failed + counts.unknown,
                    lease_until=None,
                    available_at=utc_now()
                    + timedelta(seconds=(result.retry_after or 5) + 1)
                    if result.status == "rate_limited"
                    else None,
                ),
            )

    async def finish(self, job: MediaJobModel) -> None:
        async with transaction():
            current = await self.jobs.record(job.id, lock=True)
            if current.status == "cancelled":
                return
            counts = await self.reader.counts(job.id)
            status = (
                "completed"
                if counts.sent == job.total
                else "partial"
                if counts.sent
                else "failed"
            )
            await self.jobs.change(
                job.id,
                MediaJobChange(
                    status=status,
                    sent=counts.sent,
                    failed=counts.failed + counts.unknown,
                ),
            )
        await self.gateway.notify(
            job.owner_id,
            f"🏁 <b>#{job.id} · پایان دانلود</b>\n"
            f"✅ ارسال‌شده: {counts.sent}\n⚠️ ناموفق: {counts.failed}\n"
            f"❔ ارسال نامشخص: {counts.unknown}\n"
            "🧹 فایل‌های موقت پاک شدند.\n"
            f"📋 /status {job.id}",
        )

from papilio.infra.db.transaction import transaction

from src.modules.media.delivery.interfaces import IMediaGateway
from src.modules.media.downloads.domain.dtos import MediaJobChange
from src.modules.media.downloads.infra.readers import MediaReader
from src.modules.media.downloads.interfaces import IMediaJobService
from src.modules.ops.guards.interfaces import IPortalGuard


class MediaCompletion:
    def __init__(
        self,
        jobs: IMediaJobService,
        reader: MediaReader,
        gateway: IMediaGateway,
        guard: IPortalGuard,
    ):
        self.jobs = jobs
        self.reader = reader
        self.gateway = gateway
        self.guard = guard

    async def refresh(self, job_id: int) -> None:
        async with transaction():
            await self.guard.lock("media-dispatch")
            job = await self.jobs.record(job_id, lock=True)
            if job.status not in {"queued", "running"}:
                return
            counts = await self.reader.counts(job_id)
            status = (
                "running"
                if counts.pending
                else "completed"
                if counts.sent == job.total
                else "partial"
                if counts.sent
                else "failed"
            )
            await self.jobs.change(
                job_id,
                MediaJobChange(
                    status=status,
                    sent=counts.sent,
                    failed=counts.failed + counts.unknown,
                    lease_until=None,
                ),
            )
            owner_id = job.owner_id
        if not counts.pending:
            await self.gateway.notify(
                owner_id,
                f"🏁 <b>#{job_id} · پایان دانلود</b>\n"
                f"✅ ارسال‌شده: {counts.sent}\n⚠️ ناموفق: {counts.failed}\n"
                f"❔ ارسال نامشخص: {counts.unknown}\n"
                "🧹 فایل‌های موقت پاک شدند.\n"
                f"📋 /status {job_id}",
            )

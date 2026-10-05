import logging
from datetime import timedelta
from time import monotonic

from papilio.infra.db.transaction import transaction

from portal_contracts.media import MediaPolicy
from src.modules.media.delivery.interfaces import IMediaGateway
from src.modules.media.downloads.domain.dtos import MediaJobChange
from src.modules.media.downloads.interfaces import (
    IMediaItemService,
    IMediaJobService,
    IMediaQueue,
)
from src.modules.media.sources.app.strategy import MediaSourceStrategy
from src.modules.media.sources.domain.dtos import SourceJob
from src.modules.media.sources.interfaces import IMediaSourcePlanner
from src.modules.media.storage.infra.files import MediaFiles
from src.modules.media.storage.interfaces import IMediaWorkspace
from src.shared.dates import utc_now

logger = logging.getLogger(__name__)


class MediaPlanner:
    def __init__(
        self,
        jobs: IMediaJobService,
        items: IMediaItemService,
        downloader: IMediaSourcePlanner,
        files: MediaFiles,
        gateway: IMediaGateway,
        policy: MediaPolicy,
        workspace: IMediaWorkspace,
        queue: IMediaQueue,
        sources: MediaSourceStrategy,
    ):
        self.jobs = jobs
        self.items = items
        self.downloader = downloader
        self.files = files
        self.gateway = gateway
        self.policy = policy
        self.workspace = workspace
        self.queue = queue
        self.sources = sources

    async def execute(self, job_id: int) -> None:
        async with transaction():
            row = await self.jobs.record(job_id, lock=True)
            if row.status != "queued" or row.total or not self.policy.enabled:
                return
            job = row.model_copy()
            await self.jobs.change(
                job_id,
                MediaJobChange(
                    status="planning",
                    lease_until=utc_now()
                    + timedelta(seconds=self.policy.item_timeout_seconds + 60),
                ),
            )
        started = monotonic()
        try:
            await self.workspace.prepare(job_id)
            source = SourceJob.model_validate(job, from_attributes=True)
            plan = await self.downloader.plan(
                source, self.sources.stages(source)
            )
            if (
                not plan.items
                or len(plan.items) > self.policy.max_playlist_items
            ):
                raise ValueError("Empty or oversized media collection")
            async with transaction():
                current = await self.jobs.record(job_id, lock=True)
                if current.status == "cancelled":
                    return
                await self.items.create_many(job_id, plan)
                await self.jobs.change(
                    job_id,
                    MediaJobChange(
                        status="queued",
                        total=len(plan.items),
                        lease_until=None,
                    ),
                )
            await self.gateway.notify(
                job.owner_id,
                f"📦 <b>#{job_id}</b> · {len(plan.items)} فایل شناسایی شد\n"
                "🚀 دانلود و ارسال شروع شد.\n"
                f"🛑 /cancel {job_id}",
            )
        except Exception as exc:
            async with transaction():
                current = await self.jobs.record(job_id, lock=True)
                if current.status != "cancelled":
                    await self.jobs.change(
                        job_id,
                        MediaJobChange(
                            status="failed",
                            lease_until=None,
                            error=type(exc).__name__ + ": " + str(exc)[:350],
                        ),
                    )
            await self.gateway.notify(
                job.owner_id,
                f"⚠️ درخواست <b>#{job_id}</b> انجام نشد.\n"
                "🔐 ممکن است منبع نیازمند ورود باشد یا پاسخ ندهد.\n"
                f"📋 جزئیات: /status {job_id}",
            )
        finally:
            logger.info(
                "media_plan job=%s seconds=%.3f", job_id, monotonic() - started
            )
            await self.files.remove_plan(job_id)
            await self.queue.dispatch()

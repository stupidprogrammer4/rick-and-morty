from datetime import timedelta
from urllib.parse import urlsplit

from papilio.infra.db.transaction import transaction

from portal_contracts.media import (
    MediaAccepted,
    MediaCreate,
    MediaJobOut,
    MediaPolicy,
)
from src.modules.media.domain.dtos import MediaJobChange
from src.modules.media.infra.readers import MediaReader
from src.modules.media.interfaces import IMediaJobService
from src.modules.ops.interfaces import IPortalGuard
from src.shared.dates import utc_now
from src.shared.errors import conflict


def media_provider(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    for domain, provider in (
        ("instagram.com", "instagram"),
        ("youtube.com", "youtube"),
        ("youtu.be", "youtube"),
        ("soundcloud.com", "soundcloud"),
        ("spotify.com", "spotify"),
    ):
        if host == domain or host.endswith("." + domain):
            return provider
    return "video"


class MediaCommands:
    def __init__(
        self,
        jobs: IMediaJobService,
        reader: MediaReader,
        guard: IPortalGuard,
        policy: MediaPolicy,
    ):
        self.jobs = jobs
        self.reader = reader
        self.guard = guard
        self.policy = policy

    async def accept(self, data: MediaCreate) -> MediaAccepted:
        provider = media_provider(data.url)
        if not self.policy.enabled or provider not in self.policy.providers:
            raise conflict("دانلود این منبع فعلاً غیرفعال است.")
        async with transaction():
            await self.guard.lock("media-admission")
            result = await self.jobs.create(data, provider)
            if not result.duplicate:
                counts = await self.reader.admission(
                    data.owner_id, utc_now() - timedelta(hours=1)
                )
                if (
                    counts.active_user > self.policy.active_per_user
                    or counts.active_global > self.policy.active_global
                    or counts.recent_user > self.policy.requests_per_hour
                ):
                    raise conflict(
                        "سقف درخواست‌ها پر شده؛ کمی بعد دوباره امتحان کن."
                    )
        return result

    async def cancel(self, id: int, owner_id: int) -> MediaJobOut:
        async with transaction():
            job = await self.jobs.record(id, lock=True)
            await self.jobs.get(id, owner_id)
            if job.status not in {"queued", "planning", "running"}:
                raise conflict("این دانلود دیگر قابل لغو نیست.")
            await self.jobs.change(id, MediaJobChange(status="cancelled"))
        result = await self.jobs.get(id, owner_id)
        return result

import asyncio
from zoneinfo import ZoneInfo

from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import PortalConfiguration
from src.modules.content.publications.app.policy import PublicationPolicy
from src.modules.content.publications.infra.mysql import PublicationRepository
from src.modules.ops.guards.interfaces import IPortalGuard
from src.shared.dates import utc_now


class PublicationRecovery:
    def __init__(
        self,
        repo: PublicationRepository,
        guard: IPortalGuard,
        settings: PortalConfiguration,
    ):
        self.repo = repo
        self.guard = guard
        self.settings = settings
        self.policy = PublicationPolicy(settings.portal)

    async def enqueue_pending(self) -> None:
        from src.modules.content.publications.tasks.schedulers import dispatch

        async with transaction():
            now = utc_now()
            guard = await self.guard.lock("publishing")
            await self.repo.recover_sending(now)
            await self.repo.expire_queued(now)
            if guard.paused or self.policy.quiet(now):
                return
            day = now.astimezone(
                ZoneInfo(self.settings.portal.timezone)
            ).date()
            used = await self.repo.day_count(day)
            slots = self.settings.portal.daily_post_cap - used
            if slots <= 0:
                return
            rows = await self.repo.due(now, slots)
            ids = [row.id for row in rows]
        await asyncio.gather(
            *(
                dispatch.DispatchPublication.enqueue(publication_id=id)
                for id in ids
            )
        )

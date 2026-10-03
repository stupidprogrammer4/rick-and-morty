from zoneinfo import ZoneInfo

from portal_contracts.configuration import PortalConfiguration
from src.modules.ops.domain.dtos import PortalStatus
from src.modules.ops.infra.readers import (
    DatabaseHealthReader,
    QueueStatusReader,
)
from src.modules.ops.interfaces import IPortalGuard
from src.shared.dates import utc_now


class PortalStatusQuery:
    def __init__(
        self,
        guard: IPortalGuard,
        settings: PortalConfiguration,
        reader: DatabaseHealthReader,
        queues: QueueStatusReader,
    ):
        self.guard = guard
        self.settings = settings
        self.reader = reader
        self.queues = queues

    async def get(self) -> PortalStatus:
        available = await self.reader.available()
        paused = await self.guard.is_paused()
        day = (
            utc_now()
            .astimezone(ZoneInfo(self.settings.portal.timezone))
            .date()
        )
        queues = await self.queues.read(day)
        return PortalStatus(
            database=available,
            paused=paused,
            dry_run=self.settings.portal.dry_run,
            ai_mode=self.settings.ai.mode,
            model_configured=bool(self.settings.ai.model),
            market_enabled=self.settings.market.enabled,
            daily_post_cap=self.settings.portal.daily_post_cap,
            queues=queues,
        )

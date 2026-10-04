from datetime import datetime, timedelta

from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import ContentSchedule, PortalConfiguration
from portal_contracts.enums import BotRole
from src.config.settings import PortalAppSettings
from src.modules.automation.missions.domain.dtos import ScheduledMissionCreate
from src.modules.automation.missions.interfaces import IMissionService
from src.modules.ops.guards.interfaces import IPortalGuard
from src.shared.dates import utc_now


def current_slot(rule: ContentSchedule, now: datetime) -> datetime | None:
    if not rule.enabled or now < rule.starts_at:
        return None
    elapsed = int((now - rule.starts_at).total_seconds())
    return rule.starts_at + timedelta(
        seconds=(elapsed // rule.interval_seconds) * rule.interval_seconds
    )


class ScheduledMissionCommands:
    def __init__(
        self,
        missions: IMissionService,
        guard: IPortalGuard,
        settings: PortalConfiguration,
        runtime: PortalAppSettings,
    ):
        self.missions = missions
        self.guard = guard
        self.settings = settings
        self.runtime = runtime

    async def tick(self) -> None:
        policy = self.settings.automation
        owner = policy.owner_id
        if (
            owner is None
            or owner not in self.runtime.security.admin_ids
            or self.settings.portal.channel_id is None
            or await self.guard.is_paused()
        ):
            return
        # One owner admission lock preserves the shared mission capacity.
        async with transaction():
            await self.guard.lock(f"missions:{owner}")
            await self.admit("news", BotRole.RICK, policy.news, owner)
            await self.admit("prices", BotRole.MORTY, policy.prices, owner)

    async def admit(
        self, intent: str, role: BotRole, rule: ContentSchedule, owner: int
    ) -> None:
        slot = current_slot(rule, utc_now())
        if slot is None or (
            intent == "prices" and not self.settings.market.enabled
        ):
            return
        await self.missions.create_scheduled(
            ScheduledMissionCreate(
                owner_id=owner,
                role=role,
                intent=intent,
                text=rule.prompt,
                scheduled_at=slot,
            )
        )

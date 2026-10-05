from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import ContentSchedule, PortalConfiguration
from portal_contracts.enums import BotRole
from portal_contracts.occasions import OccasionPolicy
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


def occasion_slot(
    rule: OccasionPolicy, timezone: str, now: datetime
) -> datetime | None:
    if not rule.enabled:
        return None
    local = now.astimezone(ZoneInfo(timezone))
    slot = datetime.combine(local.date(), rule.time, local.tzinfo)
    end = datetime.combine(local.date(), rule.publish_end, local.tzinfo)
    return slot.astimezone(UTC) if slot <= local <= end else None


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
            self.settings.portal.channel_id is None
            or await self.guard.is_paused()
        ):
            return
        occasions = self.settings.occasions
        occasion_owner = occasions.owner_id
        slot = occasion_slot(
            occasions, self.settings.portal.timezone, utc_now()
        )
        if (
            slot is not None
            and occasion_owner in self.runtime.security.admin_ids
            and occasion_owner is not None
        ):
            async with transaction():
                await self.guard.lock(f"missions:{occasion_owner}")
                await self.missions.create_scheduled(
                    ScheduledMissionCreate(
                        owner_id=occasion_owner,
                        role=BotRole.RICK,
                        intent="occasions",
                        text=occasions.prompt,
                        scheduled_at=slot,
                    )
                )
        if owner is None or owner not in self.runtime.security.admin_ids:
            return
        # One owner admission lock preserves the shared mission capacity.
        async with transaction():
            await self.guard.lock(f"missions:{owner}")
            await self.admit("news", BotRole.RICK, policy.news, owner)
            await self.admit("prices", BotRole.MORTY, policy.prices, owner)
            await self.admit("charts", BotRole.MORTY, policy.charts, owner)

    async def admit(
        self,
        intent: Literal["news", "prices", "charts"],
        role: BotRole,
        rule: ContentSchedule,
        owner: int,
    ) -> None:
        slot = current_slot(rule, utc_now())
        if (
            slot is None
            or (intent == "prices" and not self.settings.market.enabled)
            or (intent == "charts" and not self.settings.market.charts.enabled)
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

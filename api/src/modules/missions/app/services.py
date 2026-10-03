from datetime import timedelta

from papilio.infra.db.tools.decorators import transactional

from portal_contracts.configuration import PortalConfiguration
from portal_contracts.missions import (
    MissionAccepted,
    MissionCreate,
    MissionOut,
    MissionPage,
    PageRequest,
)
from src.modules.missions.domain.dtos import (
    MissionChange,
    ScheduledMissionCreate,
)
from src.modules.missions.domain.models import MissionModel
from src.modules.missions.infra.mysql import MissionRepository
from src.shared.dates import utc_now
from src.shared.errors import conflict, forbidden, missing


class MissionService:
    def __init__(self, repo: MissionRepository, settings: PortalConfiguration):
        self.repo = repo
        self.settings = settings

    @transactional
    async def create_scheduled(self, data: ScheduledMissionCreate) -> None:
        # Negative bot IDs are reserved for internal schedules, never Telegram.
        bot_id = -1 if data.intent == "news" else -2
        slot = int(data.scheduled_at.timestamp() * 1_000_000)
        existing = await self.repo.by_update(bot_id, slot)
        if existing is not None:
            return
        count = await self.repo.active_count(data.owner_id)
        if count >= self.settings.portal.mission_concurrency:
            return
        await self.repo.create(
            MissionModel(
                owner_id=data.owner_id,
                origin_chat_id=data.owner_id,
                origin_bot=data.role,
                origin_message_id=0,
                bot_id=bot_id,
                update_id=slot,
                actor=data.role,
                intent=data.intent,
                text=data.text,
                automation_key=f"{data.intent}:{slot}",
                deadline=utc_now()
                + timedelta(seconds=self.settings.portal.mission_timeout),
            )
        )

    @transactional
    async def create(self, data: MissionCreate) -> MissionAccepted:
        existing = await self.repo.by_update(data.bot_id, data.update_id)
        if existing is not None:
            if existing.owner_id != data.owner_id:
                raise forbidden()
            return MissionAccepted(
                mission=MissionOut.model_validate(
                    existing, from_attributes=True
                ),
                duplicate=True,
            )
        count = await self.repo.active_count(data.owner_id)
        if count >= self.settings.portal.mission_concurrency:
            raise conflict("تعداد مأموریت‌های فعال به سقف رسیده.")
        now = utc_now()
        mission = await self.repo.create(
            MissionModel(
                **data.model_dump(mode="json"),
                deadline=now
                + timedelta(seconds=self.settings.portal.mission_timeout),
            )
        )
        return MissionAccepted(
            mission=MissionOut.model_validate(mission, from_attributes=True)
        )

    async def get(self, id: int, owner_id: int) -> MissionOut:
        mission = await self.repo.get(id)
        if mission is None or mission.owner_id != owner_id:
            raise missing("mission", id)
        return MissionOut.model_validate(mission, from_attributes=True)

    async def page(self, owner_id: int, data: PageRequest) -> MissionPage:
        rows, total = await self.repo.page(
            owner_id, (data.page - 1) * data.per_page, data.per_page
        )
        return MissionPage(
            items=[
                MissionOut.model_validate(row, from_attributes=True)
                for row in rows
            ],
            total=total,
            **data.model_dump(),
        )

    @transactional
    async def cancel(self, id: int, owner_id: int) -> MissionOut:
        mission = await self.repo.get(id, lock=True)
        if mission is None or mission.owner_id != owner_id:
            raise missing("mission", id)
        if mission.status not in {"queued", "running", "waiting"}:
            raise conflict("این مأموریت قابل لغو نیست.")
        await self.repo.change(
            id, MissionChange(status="cancelled", stage="cancelled")
        )
        result = await self.get(id, owner_id)
        return result
